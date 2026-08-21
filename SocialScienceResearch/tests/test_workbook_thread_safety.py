"""Thread-safety of the shared Excel workbook store.

The API serves background jobs (JobManager worker threads) and request
handlers concurrently against a single ``WorkbookStore``; every mutation must
be serialized by the store lock so readers never observe torn state.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from SocialScienceResearch.config.settings import RepositorySettings
from SocialScienceResearch.domain.models import Comment, Video
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories


def _make_repos(tmp_path):
    rs = RepositorySettings(data_dir=str(tmp_path), dataset_name="conc")
    return build_excel_repositories(rs)


def test_concurrent_upserts_do_not_lose_rows(tmp_path) -> None:
    repos = _make_repos(tmp_path)
    workers = 4
    rows_per_worker = 25
    barrier = threading.Barrier(workers)

    def writer(worker_id: int) -> None:
        barrier.wait()
        for i in range(rows_per_worker):
            repos.videos.upsert_video(
                Video(
                    video_id=f"v_{worker_id}_{i}",
                    url=f"https://www.youtube.com/watch?v=v_{worker_id}_{i}",
                    channel_id="UCconc00000000000000000000",
                    title=f"Video {worker_id}-{i}",
                    first_observed_run_id="r_conc",
                )
            )

    threads = [threading.Thread(target=writer, args=(w,)) for w in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive(), "writer thread deadlocked"

    rows = repos.videos.list_videos(channel_id="UCconc00000000000000000000")
    assert len(rows) == workers * rows_per_worker
    ids = {v.video_id for v in rows}
    assert len(ids) == workers * rows_per_worker
    repos.store.close()


def test_concurrent_reads_during_writes_are_consistent(tmp_path) -> None:
    repos = _make_repos(tmp_path)
    for i in range(10):
        repos.videos.upsert_video(
            Video(
                video_id=f"seed_{i}",
                url=f"https://www.youtube.com/watch?v=seed_{i}",
                channel_id="UCconc00000000000000000000",
                title=f"Seed {i}",
                first_observed_run_id="r_conc",
            )
        )

    stop = threading.Event()
    observed_counts: list[int] = []

    def reader() -> None:
        while not stop.is_set():
            count = len(repos.videos.list_videos(channel_id="UCconc00000000000000000000"))
            observed_counts.append(count)
            time.sleep(0.001)

    readers = [threading.Thread(target=reader) for _ in range(3)]
    for t in readers:
        t.start()

    def writer() -> None:
        for i in range(20):
            repos.videos.upsert_video(
                Video(
                    video_id=f"extra_{i}",
                    url=f"https://www.youtube.com/watch?v=extra_{i}",
                    channel_id="UCconc00000000000000000000",
                    title=f"Extra {i}",
                    first_observed_run_id="r_conc",
                )
            )
            time.sleep(0.002)

    writer_thread = threading.Thread(target=writer)
    writer_thread.start()
    writer_thread.join(timeout=30)
    assert not writer_thread.is_alive(), "writer deadlocked"
    time.sleep(0.05)
    stop.set()
    for t in readers:
        t.join(timeout=10)

    final = len(repos.videos.list_videos(channel_id="UCconc00000000000000000000"))
    assert final == 30  # 10 seeds + 20 extras, none lost
    assert all(0 <= n <= 30 for n in observed_counts)
    repos.store.close()


def test_mixed_mutations_across_sheets_serialized(tmp_path) -> None:
    repos = _make_repos(tmp_path)

    def write_video(i: int) -> None:
        repos.videos.upsert_video(
            Video(
                video_id=f"mix_v_{i}",
                url=f"https://www.youtube.com/watch?v=mix_v_{i}",
                channel_id="UCconc00000000000000000000",
                title=f"Mix {i}",
                first_observed_run_id="r_conc",
            )
        )

    def write_comment(i: int) -> None:
        repos.comments.upsert_comment(
            Comment(
                comment_id=f"mix_c_{i}",
                video_id="mix_v_0",
                first_observed_run_id="r_conc",
            )
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(write_video, i) if i % 2 == 0 else pool.submit(write_comment, i)
            for i in range(40)
        ]
        for future in as_completed(futures):
            future.result(timeout=30)

    videos = repos.videos.list_videos(channel_id="UCconc00000000000000000000")
    comments = repos.comments.list_comments("mix_v_0")
    assert len(videos) == 20
    assert len(comments) == 20
    repos.store.close()