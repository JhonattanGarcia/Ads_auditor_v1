CREATE TABLE queue_clears (
 source TEXT NOT NULL,
 ad_id TEXT NOT NULL,
 client_id TEXT NOT NULL,
 cleared_through TEXT NOT NULL,
 PRIMARY KEY(source,ad_id,client_id),
 FOREIGN KEY(source,ad_id) REFERENCES ads(source,ad_id)
);
