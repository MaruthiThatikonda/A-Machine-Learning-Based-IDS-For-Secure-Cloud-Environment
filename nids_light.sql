CREATE TABLE predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts REAL,
                        src_ip TEXT,
                        dst_ip TEXT,
                        features TEXT,
                        supervised_prob REAL,
                        unsupervised_score REAL,
                        attack_score REAL,
                        label INTEGER,
                        true_label INTEGER,
                        latency_ms REAL
                    , reason TEXT);

CREATE TABLE sqlite_sequence(name,seq);

CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT
                    );

