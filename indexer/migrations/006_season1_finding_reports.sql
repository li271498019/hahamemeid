-- Season 1 finding report publication: the submitter publishes their report
-- text through POST /v1/season1/findings/{hash}/report. The server verifies
-- keccak256(content) == report_evidence_hash before storing, so only the
-- submitter (who holds the report bytes) can publish it. The salt is never
-- sent and never stored. Adopted/reason stay out of this table: adoption is
-- a reviewer decision, published separately.
CREATE TABLE IF NOT EXISTS season1_finding_reports (
    report_evidence_hash BYTEA PRIMARY KEY REFERENCES season1_findings(report_evidence_hash),
    report_id            TEXT NOT NULL,
    title                TEXT NOT NULL,
    content              TEXT NOT NULL,
    published_at         BIGINT NOT NULL
);
ALTER TABLE season1_finding_reports OWNER TO haha;
