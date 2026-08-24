CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO tasks (title, done)
SELECT 'Complete Assignment', FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM tasks
);

INSERT INTO tasks (title, done)
SELECT 'Practice DSA', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM tasks WHERE title = 'Practice DSA'
);

INSERT INTO tasks (title, done)
SELECT 'Read FastAPI Docs', FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM tasks WHERE title = 'Read FastAPI Docs'
);