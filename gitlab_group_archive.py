#!/usr/bin/env python3
"""
gitlab_group_archive.py

Archive all projects in a GitLab group into zip files containing:
 - a mirrored git repo (git clone --mirror)
 - mirrored wiki (if available)
 - JSON exports of issues, merge requests, labels, milestones, releases, tags
 - small README metadata

Usage examples:
  # quick test on a single project id
  GITLAB_TOKEN=xxxx python gitlab_group_archive.py --gitlab https://gitlab.example.edu --group-id 123 --project-ids 456 --outdir ./archives

  # archive entire group
  GITLAB_TOKEN=xxxx python gitlab_group_archive.py --gitlab https://gitlab.example.edu --group-path billingegroup --outdir ./archives

Notes:
 - Requires 'git' installed and available in PATH.
 - For private GitLab instances, use the instance base URL in --gitlab.
"""
import argparse
import os
import sys
import requests
import subprocess
import tempfile
import shutil
import json
import time
from urllib.parse import urljoin, quote_plus
from pathlib import Path

# ---------- Configurable defaults ----------
PER_PAGE = 100
REQUEST_SLEEP = 0.35  # sleep between API calls to be polite
# -------------------------------------------

def api_get(session, base, path, params=None):
    url = base.rstrip('/') + '/api/v4' + path
    results = []
    page = 1
    while True:
        p = dict(params or {})
        p.update({'per_page': PER_PAGE, 'page': page})
        r = session.get(url, params=p, timeout=60)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            return data
        results.extend(data)
        # pagination
        next_page = r.headers.get('X-Next-Page')
        if not next_page:
            break
        page = int(next_page)
        time.sleep(REQUEST_SLEEP)
    return results

def safe_run(cmd, cwd=None, env=None):
    # Runs a shell command, raising on error with combined output if fails
    proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nOutput:\n{proc.stdout}")
    return proc.stdout

def clone_mirror(repo_url, dest_dir, token=None):
    """
    Clone a repo as a mirror into dest_dir (a path that will contain the bare repo directory).
    repo_url should be an HTTP(S) URL (or SSH). If token is provided and repo_url is http,
    token will be injected as oauth2:<token> for GitLab bearer access.
    Returns path to created mirror dir.
    """
    # Determine clone URL to use
    url_to_use = repo_url
    if token and repo_url.startswith('http'):
        # inject token for GitLab: use oauth2 token username
        # pattern: https://oauth2:TOKEN@gitlab.example.edu/namespace/repo.git
        parts = repo_url.split('://', 1)
        if len(parts) == 2:
            scheme, rest = parts
            url_to_use = f"{scheme}://oauth2:{token}@{rest}"
    # run git clone --mirror into parent dest_dir/<name>.git
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    # build repo dir name
    repo_name = repo_url.rstrip('/').split('/')[-1]
    if not repo_name.endswith('.git'):
        repo_name += '.git'
    repo_path = dest_dir / repo_name
    if repo_path.exists():
        # if exists, try to fetch updates
        try:
            safe_run(['git', '--version'])
            safe_run(['git', 'remote', 'update'], cwd=str(repo_path))
            return str(repo_path)
        except Exception:
            shutil.rmtree(str(repo_path))
    safe_run(['git', 'clone', '--mirror', url_to_use, str(repo_path)])
    return str(repo_path)

def fetch_project_metadata(session, api_base, project_id):
    meta = {}
    # project details
    meta['project'] = api_get(session, api_base, f'/projects/{project_id}')
    # issues (open and closed)
    meta['issues'] = api_get(session, api_base, f'/projects/{project_id}/issues', params={'scope': 'all'})
    # merge requests
    meta['merge_requests'] = api_get(session, api_base, f'/projects/{project_id}/merge_requests', params={'scope': 'all'})
    # labels
    meta['labels'] = api_get(session, api_base, f'/projects/{project_id}/labels')
    # milestones
    meta['milestones'] = api_get(session, api_base, f'/projects/{project_id}/milestones')
    # releases
    meta['releases'] = api_get(session, api_base, f'/projects/{project_id}/releases')
    # tags (git tags) via API
    meta['tags'] = api_get(session, api_base, f'/projects/{project_id}/repository/tags')
    # pipelines - optional, might be heavy; comment out if not wanted
    try:
        meta['pipelines'] = api_get(session, api_base, f'/projects/{project_id}/pipelines')
    except Exception:
        meta['pipelines'] = None
    return meta

def archive_project(session, api_base, project, outdir, token=None, dry_run=False):
    """
    project: dict from /groups/:id/projects listing (contains id, path_with_namespace, http_url_to_repo, ssh_url_to_repo)
    outdir: base output directory (existing)
    """
    proj_id = project['id']
    path_with_ns = project['path_with_namespace']
    safe_name = path_with_ns.replace('/', '__')
    project_dir = Path(outdir) / f"{safe_name}-{proj_id}"
    project_dir.mkdir(parents=True, exist_ok=True)
    log = {'id': proj_id, 'path': path_with_ns, 'status': 'started', 'messages': []}
    try:
        # metadata fetch
        log['messages'].append('fetching metadata')
        meta = fetch_project_metadata(session, api_base, proj_id)
        with open(project_dir / 'metadata.json', 'w', encoding='utf8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # mirror repo
        log['messages'].append('cloning mirror repo')
        repo_url = project.get('http_url_to_repo') or project.get('ssh_url_to_repo')
        if not repo_url:
            raise RuntimeError('No repo url found')
        if dry_run:
            log['messages'].append(f"dry-run: would clone {repo_url}")
            mirror_path = None
        else:
            mirror_path = clone_mirror(repo_url, project_dir, token=token)
            log['messages'].append(f"cloned mirror into {mirror_path}")

        # attempt wiki clone if enabled
        wiki_enabled = project.get('wiki_enabled', False)
        if wiki_enabled:
            # construct wiki repo url: replace .git with .wiki.git
            log['messages'].append('attempting wiki clone')
            if repo_url.endswith('.git'):
                wiki_url = repo_url[:-4] + '.wiki.git'
            else:
                wiki_url = repo_url + '.wiki.git'
            try:
                if dry_run:
                    log['messages'].append(f"dry-run: would clone wiki {wiki_url}")
                else:
                    wiki_path = clone_mirror(wiki_url, project_dir, token=token)
                    log['messages'].append(f"cloned wiki into {wiki_path}")
            except Exception as e:
                log['messages'].append(f"wiki clone failed: {e}")

        # write README summary
        summary = {
            'id': proj_id,
            'path_with_namespace': path_with_ns,
            'name': project.get('name'),
            'web_url': project.get('web_url'),
            'archived_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        with open(project_dir / 'README.archive.json', 'w', encoding='utf8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # zip the project_dir into outdir/<safe_name>-<id>.zip
        zipname = Path(outdir) / f"{safe_name}-{proj_id}.zip"
        if dry_run:
            log['messages'].append(f"dry-run: would create {zipname}")
        else:
            # ensure any existing zip removed
            if zipname.exists():
                zipname.unlink()
            base = str(project_dir.parent)
            root = str(project_dir.name)
            # using shutil.make_archive easier: it creates zip of folder
            shutil.make_archive(base_name=str(zipname.with_suffix('')), format='zip', root_dir=base, base_dir=root)
            log['messages'].append(f"created archive {zipname}")

        log['status'] = 'done'
    except Exception as exc:
        log['status'] = 'failed'
        log['messages'].append(f"error: {repr(exc)}")
    return log

def main():
    parser = argparse.ArgumentParser(description="Archive GitLab group projects into zip files.")
    parser.add_argument('--gitlab', required=True, help="GitLab base URL, e.g. https://gitlab.example.edu or https://gitlab.com")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--group-id', type=int, help='GitLab group numeric id')
    group.add_argument('--group-path', help='GitLab group path (e.g. billingegroup)')
    parser.add_argument('--token', help='GitLab personal access token (or set GITLAB_TOKEN env var)')
    parser.add_argument('--outdir', default='./gitlab_archives', help='Output directory')
    parser.add_argument('--project-ids', nargs='+', type=int, help='List of project IDs to archive instead of entire group (useful for testing)')
    parser.add_argument('--dry-run', action='store_true', help='Do not clone or write archives; only simulate')
    args = parser.parse_args()

    token = args.token or os.environ.get('GITLAB_TOKEN')
    if not token:
        print("ERROR: a GitLab token is required via --token or GITLAB_TOKEN env var", file=sys.stderr)
        sys.exit(2)

    # create session
    session = requests.Session()
    session.headers.update({'PRIVATE-TOKEN': token, 'User-Agent': 'gitlab-group-archiver/1.0'})

    api_base = args.gitlab.rstrip('/')

    # get list of projects
    if args.project_ids:
        projects = []
        for pid in args.project_ids:
            try:
                p = api_get(session, api_base, f'/projects/{pid}')
                projects.append(p)
            except Exception as e:
                print(f"Failed to fetch project {pid}: {e}", file=sys.stderr)
    else:
        # get group id if path given
        gid = args.group_id
        if not gid:
            # look up group by path
            try:
                gp = api_get(session, api_base, f'/groups/{quote_plus(args.group_path)}')
                gid = gp['id']
            except Exception as e:
                print(f"Failed to find group {args.group_path}: {e}", file=sys.stderr)
                sys.exit(3)
        # now list group projects
        print(f"Listing projects in group id {gid} ...")
        projects = api_get(session, api_base, f'/groups/{gid}/projects', params={'include_subgroups': True, 'simple': True})
        print(f"Found {len(projects)} projects.")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    logs = []
    for proj in projects:
        print(f"Archiving {proj['path_with_namespace']} (id={proj['id']}) ...")
        try:
            log = archive_project(session, api_base, proj, outdir, token=token, dry_run=args.dry_run)
        except Exception as e:
            log = {'id': proj.get('id'), 'path': proj.get('path_with_namespace'), 'status': 'exception', 'messages': [repr(e)]}
        logs.append(log)
        # small pause
        time.sleep(REQUEST_SLEEP)

    # write master index
    with open(outdir / 'index.json', 'w', encoding='utf8') as f:
        json.dump({'archived_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'results': logs}, f, indent=2, ensure_ascii=False)

    print(f"Done. Archives and index saved in {outdir.resolve()}")

if __name__ == '__main__':
    main()
