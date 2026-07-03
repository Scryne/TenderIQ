-- TenderIQ — RLS'ye TABİ, süper-kullanıcı OLMAYAN uygulama rolü.
--
-- POSTGRES_USER (tenderiq) süper-kullanıcıdır ve RLS'yi baypas eder; uygulama
-- (api/worker) ASLA o rolle bağlanmaz. Migration'lar tenderiq (ayrıcalıklı),
-- runtime ise tenderiq_app (RLS'ye tabi) ile çalışır. Bkz. ADR-0003.
--
-- Not: init script'leri yalnızca boş veri hacminde (ilk kurulum) çalışır.
CREATE ROLE tenderiq_app LOGIN PASSWORD 'tenderiq_app';

GRANT USAGE ON SCHEMA public TO tenderiq_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tenderiq_app;

-- Migration'ların (tenderiq) oluşturacağı GELECEK tablolar için varsayılan yetkiler.
ALTER DEFAULT PRIVILEGES FOR ROLE tenderiq IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tenderiq_app;
