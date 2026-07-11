from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.models import CommentSnapshot
from app.db.repositories import AnalysisJobRepository
from app.db.session import build_engine, build_session_factory


def test_job_repository_allows_repeat_video_jobs_and_creates_steps(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)

    with factory.begin() as session:
        repository = AnalysisJobRepository(session)
        first = repository.create("https://youtu.be/abcdefghijk", "abcdefghijk")
        second = repository.create("abcdefghijk", "abcdefghijk")
        first_id = first.id
        second_id = second.id

    with factory() as session:
        repository = AnalysisJobRepository(session)
        assert first_id != second_id
        assert len(repository.list_steps(first_id)) == 7


def test_comment_id_is_unique_within_job(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)

    with factory.begin() as session:
        job = AnalysisJobRepository(session).create("abcdefghijk", "abcdefghijk")
        session.add_all(
            [
                CommentSnapshot(job_id=job.id, youtube_video_id="abcdefghijk", youtube_comment_id="c1"),
                CommentSnapshot(job_id=job.id, youtube_video_id="abcdefghijk", youtube_comment_id="c1"),
            ]
        )
        try:
            session.flush()
        except IntegrityError:
            return
    raise AssertionError("duplicate comment id was accepted")
