CREATE TABLE IF NOT EXISTS Groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS URLs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    is_blacklisted BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Group_URLs (
    group_id INTEGER,
    url_id INTEGER,
    PRIMARY KEY (group_id, url_id),
    FOREIGN KEY (group_id) REFERENCES Groups(id),
    FOREIGN KEY (url_id) REFERENCES URLs(id)
);

-- Seed some initial data
INSERT OR IGNORE INTO Groups (name, description) VALUES ('General', 'Default context');
