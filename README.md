# scripts
Repository containing useful scripts.

## gitlab_group_archive.py + gitlab_metadata_to_github.py

### How to Use the Archive Script
To run the archive script on single directories, you would use the following command
```
GITLAB_TOKEN=xxxx python gitlab_group_archive.py \
  --gitlab https://gitlab.example.edu \
  --project-ids 12345 67890 --outdir ./archives_test
```
This command allows for fast, safe, and controlled testing.

If you want to run the command on your entire GitLab instance, you would use the
following command
```
GITLAB_TOKEN=<YOUR_PERSONAL_ACCESS_TOKEN> python gitlab_group_archive.py \
  --gitlab https://<YOUR_GITLAB_URL> \
  --group-path <YOUR_GROUP_PATH> \
  --outdir ./gitlab_archives
```

### Migrating the Archived Files to GitHub
The way that the GitLab repositories are archived makes it very easy to
migrate the files to GitHub if you wish. Inside each unzipped archive folder
(e.g., `billingegroup__my-repo-123`), you will find a `my-repo.git` directory.
This is a bare mirror clone, and this is exactly what you need to migrate the
repository to GitHub with all history, branches, and tags intact.

To migrate a specific repository, you would
1. Create a new, empty repository on GitHub (e.g., `https://github.com/billingegroup/my-repo.git`).
2. Navigate into the bare mirror directory from your archive:
```
cd ./archives_test/billingegroup__my-repo-123/my-repo.git
```
3. Push the mirror to the new GitHub remote:
```
git push --mirror https://github.com/billingegroup/my-repo.git
```
Note that this process can also be scripted if you wish to migrate a larger
number of repositories to GitHub.

### Migrating the Issues/PRs/Milestones from GitLab to GitHub
What we've done so far is use the archive script to create a bare mirror
clone that we eventually use to push to GitHub using the ``git push --mirror``
command. A standard git mirror clone only includes the git data itself: commits,
branches, and tags. It does not include "metadata" like issues, pull requests
(merge requests in GitLab), or comments because those are part of the GitLab platform,
not the git repository. After pushing the mirror to GitHub, we must now run the 
``gitlab_metadata_to_github.py`` script to migrate the issues/PRs.

Pre-Requisites:
1. GitHub CLI: Ensure it is installed and that you are logged in (run ``gh auth login``)
2. Archive Directory: You need the folder containing your unzipped archives
(where the ``metadata.json`` files live).

Usage:
From inside your ``archives_test`` folder,
```
python gitlab_metadata_to_github.py \
  --metadata ./billingegroup__my-repo-123/metadata.json \
  --github-repo billingegroup/myrepo
```
Note that this assumes you already pushed the mirror to ``billingegroup/myrepo``.

### Automating This Process
We can use ``batch_migrate_to_github.py`` to automate this process.

Pre-Requisites:
1. You have already run your ``gitlab_group_archive.py`` script, which generated your ``index.json`` and all the project folders.
2. You have created the empty destination repositories on GitHub for each of these projects (the script assumes the URLs exist and you have push access).
3. You are logged into the GitHub CLI (``gh auth login``).

How to Use:
Point it at your archive directory and provide your destination GitHub organization name:
```
python batch_migrate_to_github.py --archive-dir ./gitlab_archives --github-org my-github-org
```

