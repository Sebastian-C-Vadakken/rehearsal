"""Upload the app to a Hugging Face Docker Space.

    python scripts/deploy_space.py <hf-username>/rehearsal --dry-run   # show exactly what would be uploaded
    python scripts/deploy_space.py <hf-username>/rehearsal             # upload

Requires `hf auth login` first, run in your own terminal. Only the allowlisted files below are uploaded,
and the upload aborts if anything that looks like a secret ends up in the staging folder.
The API key itself is a Space secret (NEBIUS_API_KEY) that you add in the Space settings.
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOW = ["Dockerfile", ".dockerignore", "LICENSE", "requirements.txt", "app", "scenarios", "static"]
SKIP_DIRS = {"__pycache__"}


def stage(dest: Path) -> list[str]:
    for name in ALLOW:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dest / name)
    shutil.copy2(ROOT / "space" / "README.md", dest / "README.md")  # Space config (sdk: docker, app_port)
    files = sorted(str(p.relative_to(dest)).replace("\\", "/") for p in dest.rglob("*") if p.is_file())
    leaks = [f for f in files if Path(f).name.startswith(".env") or Path(f).name.endswith(".env")]
    if leaks or any(part in SKIP_DIRS for f in files for part in Path(f).parts):
        sys.exit(f"Refusing to upload, unexpected files staged: {leaks}")
    return files


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1 or "/" not in args[0]:
        sys.exit(__doc__)
    repo_id, dry = args[0], "--dry-run" in sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        files = stage(Path(tmp))
        print(f"{len(files)} files staged for {repo_id}:")
        for f in files:
            print("  ", f)
        if dry:
            print("\nDry run, nothing uploaded.")
            return
        from huggingface_hub import HfApi
        api = HfApi()
        user = api.whoami()["name"]  # fails clearly if `hf auth login` hasn't been run
        print(f"\nUploading as {user}...")
        info = api.upload_folder(folder_path=tmp, repo_id=repo_id, repo_type="space",
                                 commit_message="Deploy Rehearsal", delete_patterns=["*"])
        print("Done:", info.commit_url)
        print(f"Space: https://huggingface.co/spaces/{repo_id}")


if __name__ == "__main__":
    main()
