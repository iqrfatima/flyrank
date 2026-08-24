import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


class PostgresRepository:

    def __init__(self):
        self.database_url = DATABASE_URL

    def get_connection(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row
        )

    def get_tasks(self):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM tasks ORDER BY id"
                )
                return cursor.fetchall()

    def get_task(self, task_id):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM tasks WHERE id = %s",
                    (task_id,)
                )
                return cursor.fetchone()

    def create_task(self, title):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tasks (title, done)
                    VALUES (%s, %s)
                    RETURNING *
                    """,
                    (title, False)
                )
                return cursor.fetchone()

    def update_task(self, task_id, title=None, done=None):

        with self.get_connection() as conn:
            with conn.cursor() as cursor:

                if title is not None:
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET title = %s
                        WHERE id = %s
                        """,
                        (title, task_id)
                    )

                if done is not None:
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET done = %s
                        WHERE id = %s
                        """,
                        (done, task_id)
                    )

                cursor.execute(
                    "SELECT * FROM tasks WHERE id = %s",
                    (task_id,)
                )

                return cursor.fetchone()

    def delete_task(self, task_id):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM tasks WHERE id = %s",
                    (task_id,)
                )