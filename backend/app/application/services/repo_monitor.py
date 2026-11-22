import asyncio
import logging

from app.application.events import PullRequestEvent
from app.application.ports.cache_port import CachePort
from app.application.ports.github_port import GitHubPort
from app.application.use_cases.handle_pr_event import HandlePullRequestEvent

logger = logging.getLogger(__name__)

CACHE_MONITORED_KEY = "repo_monitor:monitored_list"


class RepoMonitorService:
    """Monitors configured repositories and automatically triggers reviews

    for any new or updated pull requests.
    """

    def __init__(
        self,
        github: GitHubPort,
        cache: CachePort,
        handle_pr_event: HandlePullRequestEvent,
        poll_interval_seconds: int = 45,
    ) -> None:
        self._github = github
        self._cache = cache
        self._handle_pr_event = handle_pr_event
        self._poll_interval = poll_interval_seconds
        self._running = False

    async def get_monitored_repos(self) -> list[str]:
        data = await self._cache.get(CACHE_MONITORED_KEY)
        if isinstance(data, list):
            return data
        return []

    async def add_repo(self, repo_full_name: str) -> list[int]:
        repo = repo_full_name.strip().strip("/")
        # If full url is provided, parse it
        if "github.com/" in repo:
            repo = repo.split("github.com/")[-1].strip("/")
            # strip any /pull/.. or .git
            parts = repo.split("/")
            if len(parts) >= 2:
                repo = f"{parts[0]}/{parts[1]}"
        repo = repo.removesuffix(".git")

        current = await self.get_monitored_repos()
        if repo not in current:
            current.append(repo)
            await self._cache.set(CACHE_MONITORED_KEY, current)
            logger.info("Added repo to monitor list: %s", repo)

        # Immediately scan this repository for open PRs
        reviewed_prs = await self.scan_repo(repo)
        return reviewed_prs

    async def remove_repo(self, repo_full_name: str) -> None:
        repo = repo_full_name.strip().lower()
        current = await self.get_monitored_repos()
        filtered = [r for r in current if r.lower() != repo]
        await self._cache.set(CACHE_MONITORED_KEY, filtered)
        logger.info("Removed repo from monitor list: %s", repo_full_name)

    async def scan_repo(self, repo_full_name: str) -> list[int]:
        dispatched_prs: list[int] = []
        try:
            open_prs = await self._github.list_open_pulls(repo_full_name)
        except Exception as exc:
            logger.warning("Failed fetching open PRs for %s: %s", repo_full_name, exc)
            return []

        for pr in open_prs:
            try:
                pr_number = pr["number"]
                head_sha = pr["head"]["sha"]
                cache_key = f"repo_monitor:reviewed:{repo_full_name}:{pr_number}:{head_sha}"

                # Only review if not reviewed for this exact head commit
                if await self._cache.set_if_absent(cache_key, "1", ttl_seconds=86400 * 14):
                    logger.info(
                        "New/updated PR detected on %s: PR #%s @ %s",
                        repo_full_name,
                        pr_number,
                        head_sha[:7],
                    )
                    event = PullRequestEvent(
                        delivery_id=f"poll-{repo_full_name}-{pr_number}-{head_sha[:7]}",
                        action="synchronize",
                        repo_full_name=repo_full_name,
                        number=pr_number,
                        head_sha=head_sha,
                        base_branch=pr["base"]["ref"],
                        head_branch=pr["head"]["ref"],
                        title=pr.get("title", f"PR #{pr_number}"),
                        author=pr.get("user", {}).get("login", ""),
                        sender=pr.get("user", {}).get("login", ""),
                        draft=bool(pr.get("draft", False)),
                    )
                    await self._handle_pr_event.execute(event)
                    dispatched_prs.append(pr_number)
            except Exception as exc:
                logger.exception("Error processing PR in repo %s: %s", repo_full_name, exc)

        return dispatched_prs

    async def run_loop(self) -> None:
        self._running = True
        logger.info("Repository Listener loop started (interval: %ss)", self._poll_interval)
        while self._running:
            try:
                repos = await self.get_monitored_repos()
                for repo in repos:
                    await self.scan_repo(repo)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Error in repo listener loop: %s", exc)

            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break

    def stop(self) -> None:
        self._running = False
