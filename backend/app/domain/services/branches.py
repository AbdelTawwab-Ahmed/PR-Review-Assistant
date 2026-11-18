FIX_BRANCH_PREFIX = "prra/fix-"


def fix_branch_name(pr_number: int, head_sha: str) -> str:
    return f"{FIX_BRANCH_PREFIX}pr{pr_number}-{head_sha[:7]}"


def is_bot_branch(name: str) -> bool:
    return name.startswith(FIX_BRANCH_PREFIX)