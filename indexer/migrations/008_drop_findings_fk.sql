-- Drop the FK from season1_finding_reports to season1_findings (2026-11-28).
--
-- The FK breaks handle_reorg(): TRUNCATE season1_findings fails while the FK
-- exists, the exception is caught by run_forever(), and the syncer then
-- retries the same failing reorg every 5s forever -- data stops updating and
-- nothing alerts. The FK has no protective value: the API already 404s when
-- the finding hash is unknown (POST /v1/season1/findings/{hash}/report).
-- Reports are user-published data (not derivable from raw_logs), so
-- TRUNCATE ... CASCADE is NOT an option: it would permanently delete them.
--
-- After this, reorg replay re-derives season1_findings; reports re-attach by
-- report_evidence_hash (season1_read.py uses LEFT JOIN, so a report whose
-- finding was reorged away is a harmless orphan row until it reappears).
ALTER TABLE season1_finding_reports
  DROP CONSTRAINT IF EXISTS season1_finding_reports_report_evidence_hash_fkey;
