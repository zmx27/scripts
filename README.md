# scripts
Repository containing useful scripts.

## gitlab_group_archive.py

### How to Use
To run the script on single directories, you would use the following command
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

