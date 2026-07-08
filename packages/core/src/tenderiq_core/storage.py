"""Nesne depolama (Cloudflare R2 / S3-uyumlu) — imzalı URL üretimi.

Dosyalar kiracı-ön-ekli yollarda saklanır ve erişim yalnızca süre-sınırlı imzalı
URL'lerle sağlanır (§10.2).
"""

from __future__ import annotations

import re
import unicodedata

import boto3
from botocore.config import Config as BotoConfig

from tenderiq_core.config import Settings

# Anahtar bileşeninde izin verilen karakterler dışındakiler "_" ile değiştirilir.
_KEY_COMPONENT_UNSAFE = re.compile(r"[^\w.\-() ]")


def safe_key_component(name: str, *, max_length: int = 255) -> str:
    """İstemciden gelen dosya adını depolama anahtarında güvenli tek bileşene indirger.

    Yol ayraçları ve kontrol/özel karakterler temizlenir (``a/../b.pdf`` → ``b.pdf``);
    orijinal ad DB'de (``Document.filename``) olduğu gibi saklanır.
    """
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = unicodedata.normalize("NFKC", name).strip()
    name = _KEY_COMPONENT_UNSAFE.sub("_", name)
    name = name.lstrip(".")
    return name[:max_length] or "dosya"


class StorageNotConfiguredError(RuntimeError):
    """Nesne depolama ayarları (bucket/erişim anahtarları) eksik."""


class StorageService:
    """S3-uyumlu depolama için imzalı yükleme/indirme URL'leri üretir."""

    def __init__(
        self,
        *,
        endpoint_url: str | None,
        bucket: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
        region: str,
    ) -> None:
        if not bucket:
            raise StorageNotConfiguredError("OBJECT_STORAGE_BUCKET tanımlı değil.")
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> StorageService:
        """Ayarlardan bir depolama servisi kurar (yapılandırılmamışsa hata)."""
        return cls(
            endpoint_url=settings.object_storage_endpoint_url,
            bucket=settings.object_storage_bucket,
            access_key_id=settings.object_storage_access_key_id,
            secret_access_key=settings.object_storage_secret_access_key,
            region=settings.object_storage_region,
        )

    def presigned_put_url(self, key: str, *, content_type: str, expires_in: int = 3600) -> str:
        """Yükleme (PUT) için süre-sınırlı imzalı URL üretir."""
        url: str = self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return url

    def presigned_get_url(self, key: str, *, expires_in: int = 3600) -> str:
        """İndirme (GET) için süre-sınırlı imzalı URL üretir."""
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
