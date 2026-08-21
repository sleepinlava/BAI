# Worktree views

ABI keeps publication evidence and operational recovery helpers in Git, but
they do not need to occupy every development worktree.

Enable the core-development view in the current worktree:

```bash
git sparse-checkout set --no-cone --stdin < config/worktree/core.sparse-checkout
```

Restore the complete worktree:

```bash
git sparse-checkout disable
```

Sparse-checkout state is local to each worktree. It does not delete tracked
files, change commits, or affect another worktree.
