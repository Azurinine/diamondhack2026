CREATE TABLE IF NOT EXISTS Groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS URLs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    domain TEXT,
    is_blacklisted BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Group_URLs (
    group_id INTEGER,
    url_id INTEGER,
    PRIMARY KEY (group_id, url_id),
    FOREIGN KEY (group_id) REFERENCES Groups(id),
    FOREIGN KEY (url_id) REFERENCES URLs(id)
);

CREATE TABLE IF NOT EXISTS Tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    due_date TEXT,
    source TEXT DEFAULT 'manual',
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS Task_Groups (
    task_id INTEGER,
    group_id INTEGER,
    PRIMARY KEY (task_id, group_id),
    FOREIGN KEY (task_id) REFERENCES Tasks(id),
    FOREIGN KEY (group_id) REFERENCES Groups(id)
);

-- Seed some initial data
INSERT OR IGNORE INTO Groups (name, description) VALUES ('General', 'Default context');
