"""Yerel nesne depolama yedeği: Docker'sız, R2'siz geliştirmede belge önizlemesi çalışsın.

Tarayıcı belgeyi doğrudan nesne depolamadan okur (imzalı GET → PDF.js). Yerelde R2'ye
gidildiğinde tohumlanmış belgenin baytları orada yoktur ve inceleme ekranının asıl alanı
(kaynağı vurgulanmış şartname) boş kalır. Bu betik, S3-uyumlu YEREL bir uca:

1. kovayı açar ve web origin'lerine CORS verir (``CORS_ORIGINS``),
2. veritabanındaki her belge için nesne yoksa ``scripts/fixtures/ornek-sartname.pdf``
   örneğini o anahtara yükler (kurgusal içerik; kaynak cümlesi ``seed_e2e.py`` ile eşleşir).

Uç yalnız ``localhost``/``127.0.0.1`` olabilir: betik gerçek bir kovaya ASLA yazmaz.
S3 taklidi için (proje bağımlılığı değil, geçici araç):

    uv run --no-project --with "moto[server]" moto_server -H 127.0.0.1 -p 9000
    OBJECT_STORAGE_ENDPOINT_URL=http://localhost:9000 OBJECT_STORAGE_BUCKET=tenderiq-yerel \\
      OBJECT_STORAGE_ACCESS_KEY_ID=yerel OBJECT_STORAGE_SECRET_ACCESS_KEY=yerel \\
      OBJECT_STORAGE_REGION=us-east-1 uv run python scripts/yerel_depo.py

Belge satırları kiracılar arası okunur; bu yüzden ``DATABASE_ADMIN_URL`` (RLS'yi baypas
eden ayrıcalıklı rol) kullanılır. Örnek PDF'i yeniden üretmek: ``node scripts/ornek_sartname.mjs``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text

from tenderiq_core.config import get_settings

ORNEK = Path(__file__).resolve().parent / "fixtures" / "ornek-sartname.pdf"
YEREL_HOSTLAR = {"localhost", "127.0.0.1"}


def main() -> int:
    settings = get_settings()
    endpoint = settings.object_storage_endpoint_url
    if not endpoint or urlparse(endpoint).hostname not in YEREL_HOSTLAR:
        print(f"Durdu: uç yerel değil ({endpoint!r}). Bu betik yalnız localhost'a yazar.")
        return 2
    bucket = settings.object_storage_bucket
    if not bucket:
        print("Durdu: OBJECT_STORAGE_BUCKET tanımlı değil.")
        return 2

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.object_storage_access_key_id,
        aws_secret_access_key=settings.object_storage_secret_access_key,
        region_name=settings.object_storage_region,
        config=BotoConfig(signature_version="s3v4"),
    )
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)
        print(f"kova açıldı: {bucket}")
    s3.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": list(settings.cors_origins),
                    "AllowedMethods": ["GET", "PUT", "HEAD"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )

    engine = create_engine(settings.migration_database_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT storage_key FROM document WHERE content_type = 'application/pdf'")
        ).all()
    engine.dispose()

    veri = ORNEK.read_bytes()
    yuklenen = 0
    for (key,) in rows:
        try:
            s3.head_object(Bucket=bucket, Key=key)
            continue
        except ClientError:
            pass
        s3.put_object(Bucket=bucket, Key=key, Body=veri, ContentType="application/pdf")
        yuklenen += 1
    print(f"{len(rows)} PDF belge; {yuklenen} tanesine örnek şartname yüklendi.")
    print(f"Uç: {endpoint}/{bucket}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
