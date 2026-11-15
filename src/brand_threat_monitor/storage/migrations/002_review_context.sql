ALTER TABLE review_cases ADD COLUMN client_id TEXT REFERENCES clients(client_id);
CREATE UNIQUE INDEX one_case_per_ad_context ON review_cases(source,ad_id,coalesce(client_id,''));
