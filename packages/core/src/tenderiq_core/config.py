"""Uygulama yapılandırması (12-factor): ayarlar ortam değişkenlerinden okunur."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_AUTH_SECRET_LENGTH = 32  # HS256 için RFC 7518 §3.2 önerisi

# Ollama bağlam-tavanı hesabı için karakter→token oranı (§6.9). TR metin qwen
# tokenizasyonunda ~2.5-3.5 kar/token; 3 (biraz temkinli) kullanılır — daha
# düşük değer daha AZ chunk (daha güvenli, sessiz kırpmaya karşı) demektir.
_OLLAMA_PROMPT_CHARS_PER_TOKEN = 3


class Environment(StrEnum):
    """Çalışma ortamları."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Merkezî ayarlar. Alanlar env değişkenlerinden (case-insensitive) okunur."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Uygulama ─────────────────────────────────────────────────────────────
    project_name: str = "TenderIQ"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    # NoDecode: pydantic-settings'in env değerini JSON olarak çözmesini engeller;
    # ham string aşağıdaki _split_cors_origins validator'üne gider (virgülle ayrılır).
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # ── Veri katmanı ─────────────────────────────────────────────────────────
    # Uygulama (api/worker) bağlantısı: RLS'ye TABİ, süper-kullanıcı OLMAYAN rol.
    database_url: str = "postgresql+psycopg://tenderiq_app:tenderiq_app@localhost:5432/tenderiq"
    # Migration/DDL için ayrıcalıklı bağlantı (owner/superuser). Boşsa database_url kullanılır.
    database_admin_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    # ── Nesne depolama (Cloudflare R2 / S3) ──────────────────────────────────
    object_storage_endpoint_url: str | None = None
    object_storage_bucket: str | None = None
    object_storage_access_key_id: str | None = None
    object_storage_secret_access_key: str | None = None
    object_storage_region: str = "auto"

    # ── LLM (Sprint 2.2: çıkarım ajanları, §6.7–6.9) ─────────────────────────
    # "anthropic" (ANTHROPIC_API_KEY zorunlu; production birincil) | "ollama"
    # (yerel model, http://localhost:11434 — anahtarsız dev/ucuz iterasyon,
    # golden-set kalite kapısı yine Claude ile ölçülür) | "none" (ajanlar devre
    # dışı — extracting fazı 2.1 iskelet davranışına düşer; testler/CI).
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    llm_primary_model: str = "claude-opus-4-8"
    # Non-streaming güvenli tavan (SDK HTTP zaman aşımı sınırının altında).
    llm_max_output_tokens: int = 16000
    # Şema zorlaması: şemaya uymayan çıktı hata geri bildirimiyle yeniden istenir;
    # bu tavan aşılırsa çıkarım hatayla biter (Celery faz retry'ı devralır).
    llm_schema_max_attempts: int = 3
    # Ollama (yerel sağlayıcı): OpenAI/Anthropic'ten farklı olarak API anahtarı
    # yoktur; şema zorlaması `format=<json-schema>` ile (structured outputs).
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct-q5_K_M"
    # Ollama bağlam penceresi (num_ctx): getirilen bağlam + üretim tavanı
    # (num_predict) bu pencereye sığmalıdır; aşarsa Ollama istemi sessizce KIRPAR
    # → model kaynağı göremez → grounding çöker. 8192, q5 modelle 8GB VRAM'e
    # sığar; ajan bağlam tavanı bu pencereye göre otomatik ayarlanır
    # (effective_agent_context_limit → num_ctx=8192, num_predict=4096 ⇒ ~6 chunk).
    ollama_num_ctx: int = 8192
    # Ollama'nın tek çağrıda üreteceği azami token. Claude tavanı (16000) yerel
    # modelde laptop GPU'da dakikalarca sürer ve küçük modelin "başıboş" üretime
    # (JSON dizisini kapatmayıp token tavanına kadar doldurma) girmesine yol açar;
    # 4096 tipik çıkarım çıktısına yeter ve çağrı süresini sınırlar (§6.8).
    ollama_num_predict: int = 4096

    # ── Gözlemlenebilirlik ────────────────────────────────────────────────────
    # Langfuse (Sprint 2.4, §6.11): anahtarlar boşsa LLM tracing tamamen no-op
    # (langfuse hiç import edilmez). Doldurulunca her LLM çağrısı trace edilir
    # (model, gecikme, token). `uv sync --extra langfuse` ile kurulur.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None
    # KVKK / zero-retention (§10.3): getirilen bağlam DOKÜMAN İÇERİĞİDİR. Varsayılan
    # False → Langfuse'a yalnız metadata (model/token/gecikme) gider, istem/çıktı
    # GİTMEZ. Yalnız SELF-HOSTED Langfuse'da True yapılmalıdır (içerik dışarı sızmasın).
    langfuse_capture_io: bool = False
    sentry_dsn: str | None = None

    # ── Kimlik ────────────────────────────────────────────────────────────────
    auth_secret: str | None = None

    # ── Yükleme sınırları (Sprint 1.1 güvenlik) ──────────────────────────────
    upload_max_size_bytes: int = 100 * 1024 * 1024  # 100 MB; ileride plan kotasına bağlanır
    upload_pending_ttl_hours: int = 24  # yarım kalan yüklemeler bu süreden sonra failed olur

    # ── Oran sınırlama (login/register brute-force) ──────────────────────────
    auth_rate_limit_attempts: int = 5  # e-posta başına pencere içi deneme
    auth_rate_limit_ip_attempts: int = 20  # IP başına (ofis NAT'ı için daha gevşek)
    auth_rate_limit_window_seconds: int = 300
    # Güvenilir ters-proxy sayısı: X-Forwarded-For'un SONDAN kaç girdisinin güvenilir
    # altyapı (Next proxy'si / LB) tarafından eklendiği. 0 = XFF yok sayılır (soket
    # IP'si kullanılır). Web istekleri her zaman Next proxy'sinden geldiği için
    # compose'da api servisine 1 verilir; önüne LB eklenirse artırılır (J.1).
    trusted_proxy_count: int = 0

    # ── Parsing (Sprint 1.2 hibrit hat, ADR-0011) ────────────────────────────
    # EasyOCR dil listesi (virgülle ayrılmış env: PARSING_OCR_LANGUAGES=tr,en).
    parsing_ocr_languages: Annotated[list[str], NoDecode] = ["tr", "en"]

    # ── İndeksleme (Sprint 1.3: chunking + embedding, §6.3–6.5, ADR-0008) ───
    # Chunk sınırları karakter cinsindendir; varsayılanlar
    # tenderiq_core.indexing.chunking ile aynıdır (~400-600 token hedefi).
    indexing_chunk_max_chars: int = 1800
    indexing_chunk_overlap_chars: int = 200
    # "local" (BGE-M3, süreç içi) | "managed" (ADR-0008 yükseltme yolu, henüz yok).
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-m3"
    # DB'deki vector kolonuyla SÖZLEŞMELİ boyut (migration 0006): birlikte değişir.
    embedding_dim: int = 1024
    embedding_batch_size: int = 16

    # ── Getirim (Sprint 2.1: hibrit getirim + reranker, §6.6, ADR-0012) ─────
    retrieval_semantic_top_k: int = 24  # pgvector cosine aday sayısı
    retrieval_keyword_top_k: int = 24  # BM25 aday sayısı
    retrieval_rrf_k: int = 60  # Reciprocal Rank Fusion sabiti (literatür varsayılanı)
    retrieval_rerank_candidates: int = 32  # cross-encoder'a giden en fazla aday
    retrieval_top_n: int = 8  # tek sorgunun döndürdüğü sonuç sayısı
    # Ajan başına bağlam tavanı (sorgu birleşimi sonrası). Ollama'da bu değer
    # num_ctx'e sığacak şekilde otomatik kısılır (effective_agent_context_limit,
    # §6.9) — geniş-pencereli Claude için 12 aynen kullanılır.
    retrieval_agent_context_limit: int = 12
    # "local" (CrossEncoder; sentence-transformers = kök `embedding` grubu) | "none"
    # (reranker atlanır, RRF sırası korunur — hafif ortamlar/testler için).
    retrieval_reranker_provider: str = "local"
    retrieval_reranker_model: str = "BAAI/bge-reranker-v2-m3"

    @field_validator("cors_origins", "parsing_ocr_languages", mode="before")
    @classmethod
    def _split_csv_list(cls, value: object) -> object:
        """Virgülle ayrılmış env değerini (JSON değil, düz string) listeye ayrıştırır."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _enforce_production_hardening(self) -> Self:
        """Production'da güvensiz varsayılanlarla açılışı engeller (fail-fast)."""
        if self.environment is Environment.PRODUCTION:
            if not self.auth_secret or len(self.auth_secret) < MIN_AUTH_SECRET_LENGTH:
                raise ValueError(
                    "Production'da AUTH_SECRET zorunludur ve en az "
                    f"{MIN_AUTH_SECRET_LENGTH} karakter olmalıdır "
                    "(`openssl rand -base64 32` ile üretin)."
                )
            if self.debug:
                raise ValueError("Production'da DEBUG=true olamaz.")
        return self

    @property
    def is_production(self) -> bool:
        """Ortam production mı."""
        return self.environment is Environment.PRODUCTION

    @property
    def migration_database_url(self) -> str:
        """Migration/DDL için ayrıcalıklı bağlantı (yoksa uygulama URL'ine düşer)."""
        return self.database_admin_url or self.database_url

    def effective_agent_context_limit(self) -> int:
        """Ajan başına bağlam tavanı — Ollama'da num_ctx'e sığacak şekilde kısılır (§6.9).

        Yerel modelin bağlam penceresi (num_ctx) küçüktür. Getirilen bağlam +
        üretim tavanı (num_predict) num_ctx'i aşarsa Ollama istemi SESSİZCE kırpar
        → model kaynağı göremez → grounding çöker. Bu yüzden Ollama sağlayıcıda
        bağlam tavanı, üretim tavanı ayrıldıktan sonra pencereye sığan chunk
        sayısına indirilir (Faz 2 kapısında gerçek şartnameyle doğrulandı: 12→6).
        Anthropic gibi geniş-pencereli sağlayıcılarda yapılandırılan değer aynen kullanılır.
        """
        if self.llm_provider != "ollama":
            return self.retrieval_agent_context_limit
        prompt_token_budget = max(1, self.ollama_num_ctx - self.ollama_num_predict)
        prompt_char_budget = prompt_token_budget * _OLLAMA_PROMPT_CHARS_PER_TOKEN
        fits = max(1, prompt_char_budget // self.indexing_chunk_max_chars)
        return min(self.retrieval_agent_context_limit, fits)


@lru_cache
def get_settings() -> Settings:
    """Önbelleğe alınmış tekil ayarlar örneği döndürür."""
    return Settings()
