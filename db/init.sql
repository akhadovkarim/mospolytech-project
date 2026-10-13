-- Схема БД для приложения «Генератор паролей и хэшей» (вариант N20)

CREATE TABLE IF NOT EXISTS passwords (
    id          SERIAL PRIMARY KEY,
    value       VARCHAR(128) NOT NULL,
    length      INTEGER      NOT NULL CHECK (length BETWEEN 4 AND 128),
    has_upper   BOOLEAN      NOT NULL DEFAULT FALSE,
    has_lower   BOOLEAN      NOT NULL DEFAULT FALSE,
    has_digits  BOOLEAN      NOT NULL DEFAULT FALSE,
    has_symbols BOOLEAN      NOT NULL DEFAULT FALSE,
    strength    VARCHAR(10)  NOT NULL CHECK (strength IN ('weak', 'medium', 'strong')),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hashes (
    id          SERIAL PRIMARY KEY,
    source_text TEXT        NOT NULL,
    algorithm   VARCHAR(10) NOT NULL CHECK (algorithm IN ('md5', 'sha1', 'sha256', 'sha512', 'bcrypt')),
    hash_value  TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_passwords_created_at ON passwords (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hashes_algorithm_created ON hashes (algorithm, created_at DESC);

-- Тестовые данные
INSERT INTO passwords (value, length, has_upper, has_lower, has_digits, has_symbols, strength, created_at) VALUES
    ('qwerty',                  6,  FALSE, TRUE,  FALSE, FALSE, 'weak',   NOW() - INTERVAL '7 days'),
    ('1234',                    4,  FALSE, FALSE, TRUE,  FALSE, 'weak',   NOW() - INTERVAL '6 days'),
    ('Kx7pLm2Q',                8,  TRUE,  TRUE,  TRUE,  FALSE, 'medium', NOW() - INTERVAL '5 days'),
    ('hR4!vN9@bT',              10, TRUE,  TRUE,  TRUE,  TRUE,  'medium', NOW() - INTERVAL '4 days'),
    ('wolfsnakeeagle',          14, FALSE, TRUE,  FALSE, FALSE, 'medium', NOW() - INTERVAL '3 days'),
    ('Zq8#Lm3&Pv1$Xr7!',        16, TRUE,  TRUE,  TRUE,  TRUE,  'strong', NOW() - INTERVAL '2 days'),
    ('Mn5Tq9Wx2Rk8Yb4Hc6',      18, TRUE,  TRUE,  TRUE,  FALSE, 'strong', NOW() - INTERVAL '1 day'),
    ('a1!B2@c3#D4$e5%F6^g7&H8', 24, TRUE,  TRUE,  TRUE,  TRUE,  'strong', NOW() - INTERVAL '3 hours');

INSERT INTO hashes (source_text, algorithm, hash_value, created_at) VALUES
    ('hello',          'md5',    '5d41402abc4b2a76b9719d911017c592', NOW() - INTERVAL '7 days'),
    ('password123',    'sha1',   'cbfdac6008f9cab4083784cbd1874f76618d2a97', NOW() - INTERVAL '6 days'),
    ('Привет, мир!',   'sha256', '9a0af011605a6ab9022f248fb797064a42782210ac91e834348b3ef089313e5f', NOW() - INTERVAL '5 days'),
    ('docker compose', 'sha512', '6ffc1efa6d7e6bd4a22dc0de842108bf3d0d8343622bcec791de7e2cf873fcff9afcca4e0da5c6f7872c26ad7282e8158242ec31a49d57cc7034001b3b3a7b8b', NOW() - INTERVAL '4 days'),
    ('secret',         'bcrypt', '$2b$12$wAXjHv8zk2cABBcA6TYTxuiV8iBbybXIAvkfS0y57SSTbH6yUIGnW', NOW() - INTERVAL '3 days'),
    ('mospolytech',    'md5',    'd82d9f5cf95a46e002134516cc1d9bc0', NOW() - INTERVAL '2 days'),
    ('FastAPI',        'sha256', '2dd9eb7d9f0c11864fe058aaa0f3fbae5b1887555c9bc1f9ff84877d75f446a5', NOW() - INTERVAL '1 day'),
    ('nginx',          'sha1',   '58a3ed6f2965252c6ac4957d95f7a3bdfca47101', NOW() - INTERVAL '12 hours'),
    ('PostgreSQL 16',  'sha512', 'aaeae25c06f12ab17a0a1ee79ce06fd24b56020949b2853f099b5d6f044a1c6da10865d51a8bd2408f8257bac1047d8d9547bcc8df83af6f77a64fb1a2505cde', NOW() - INTERVAL '5 hours'),
    ('qwerty',         'bcrypt', '$2b$12$nDRlR09tZYXoYqFUVmxey.m1GCrEkJ25TlA1XbdpEUpXdgSujj5jK', NOW() - INTERVAL '1 hour');
