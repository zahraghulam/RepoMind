from importlib import reload
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pytest import warns

from utils.job_db import get_connection, init_db


@dataclass
class JobRecord:
    job_id: str
    repo_url: str
    instruction: str
    status: str = "queued"
    pr_url: str | None = None
    diff_summary: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def elapsed_time(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.finished_at if self.finished_at is not None else datetime.now(UTC)
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "repo_url": self.repo_url,
            "instruction": self.instruction,
            "status": self.status,
            "pr_url": self.pr_url,
            "diff_summary": self.diff_summary,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "elapsed_time": self.elapsed_time(),
        }


class JobManager:
    def __init__(self):
        init_db()

    def create_job(self, repo_url: str, instruction: str) -> str:
        job_id = str(uuid.uuid4())

        record = JobRecord(
            job_id=job_id,
            repo_url=repo_url,
            instruction=instruction,
        )

        conn = get_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id,
                repo_url,
                instruction,
                status,
                pr_url,
                diff_summary,
                error_message,
                created_at,
                started_at,
                finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.job_id,
                record.repo_url,
                record.instruction,
                record.status,
                record.pr_url,
                record.diff_summary,
                record.error_message,
                record.created_at.isoformat(),
                None,
                None,
            ),
        )
        conn.commit()
        conn.close()

        return job_id

    def get(self, job_id: str) -> JobRecord:
        from api.errors import JobNotFoundError

        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        conn.close()

        if row is None:
            raise JobNotFoundError(job_id)

        return JobRecord(
            job_id=row["job_id"],
            repo_url=row["repo_url"],
            instruction=row["instruction"],
            status=row["status"],
            pr_url=row["pr_url"],
            diff_summary=row["diff_summary"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        )

    def update(
        self,
        record: JobRecord | str,
        **kwargs,
    ) -> None:
        """
        Update a job.

        Supports both:
            update(job_record)
        and
            update(job_id, status="running", pr_url="...")
        """

        if isinstance(record, str):
            record = self.get(record)

        for key, value in kwargs.items():
            setattr(record, key, value)

        conn = get_connection()

        conn.execute(
            """
            UPDATE jobs
            SET
                status=?,
                pr_url=?,
                diff_summary=?,
                error_message=?,
                started_at=?,
                finished_at=?
            WHERE job_id=?
            """,
            (
                record.status,
                record.pr_url,
                record.diff_summary,
                record.error_message,
                record.started_at.isoformat() if record.started_at else None,
                record.finished_at.isoformat() if record.finished_at else None,
                record.job_id,
            ),
        )

        conn.commit()
        conn.close()

    def all_jobs(self) -> dict:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM jobs").fetchall()
        conn.close()

        return {row["job_id"]: dict(row) for row in rows}

    def stats(self) -> dict:
        conn = get_connection()

        rows = conn.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status").fetchall()

        conn.close()

        stats = {
            "total": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
        }

        for row in rows:
            stats[row["status"]] = row["count"]
            stats["total"] += row["count"]

        return stats


job_manager = JobManager()
