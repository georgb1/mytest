from argparse import ArgumentParser
import gitlab
import datetime
import os

# ###
# # Arguments parser
# ###
def process_arguments() -> dict:
    parser = ArgumentParser()
    parser.add_argument(
        "-a",
        "--address",
        dest="url",
        help="Specify GitLab URL repository - should include protocol (http/s)",
        default="https://gitlab.ihsmarkit.com",
    )
    parser.add_argument(
        "-p",
        "--project",
        dest="project",
        help="specify GitLab project",
        # default="it_engineering_automation/privatecloud/cas",
        default=os.environ['GITLAB_PROJECT_ID'],
    )
    parser.add_argument(
        "-b",
        "--branch",
        dest="branch",
        help="branch default master",
        default="master",
    )
    parser.add_argument(
        "-s",
        "--since",
        dest="since",
        help="rev name from need to collect logs, by default will be selected last tag",
        default="",
    )
    parser.add_argument(
        "-u",
        "--until",
        dest="until",
        help="rev name from need to collect logs, by default will be collected until now",
        default="",
    )
    parser.add_argument(
        "-v",
        "--version",
        dest="version",
        help="Specify NEW version number or will be used last release with increment patch",
        default="",
    )
    parser.add_argument(
        "-t",
        "--token",
        dest="token",
        help="gitlab personal token for auth",
        default=os.environ['GITLAB_API_TOKEN'],
    )

    args = parser.parse_args()

    return {
        "url": args.url,
        "project": args.project,
        "branch": args.branch,
        "since": args.since,
        "until": args.until,
        "version": args.version,
        "token": args.token,
    }


def get_data_from_tag(gl_project, tag):
    if tag is not None:
        # print("tag", tag)
        gl_tags = gl_project.tags.get(f'{tag}')
        return gl_tags.commit['created_at']


def get_commits(gl_project, ref_name='master', since='', until=''):
    single_commits = gl_project.commits.list(all=True,
                                             query_parameters={"since": since, "until": until,
                                                               "ref_name": f"{ref_name}", "per_page": "2000",
                                                               "first_parent": True})
    return single_commits


def get_merge_requests_with_commits(gl_project, since,
                                    until=''):
    gl_merge_requests = gl_project.mergerequests.list(state='merged',
                                                      order_by='updated_at',
                                                      updated_after=since,
                                                      updated_before=until)
    return gl_merge_requests


def increment_version(args):
    gl = gitlab.Gitlab(args['url'], private_token=args['token'])
    gitlab_project = gl.projects.get(args['project'])

    gl_tag = gitlab_project.tags.list()[0]
    version = gl_tag.name.split('.')
    try:
        version[2] = str(int(version[2]) + 1)
    except:
        version[2] = str(int(version[2].split("-")[0]) + 1)
    return '.'.join(version)


def generate_changelog(args):
    gl = gitlab.Gitlab(args['url'], private_token=args['token'])
    gitlab_project = gl.projects.get(args['project'])
    now = datetime.datetime.now()
    date_time = now.strftime("%Y-%m-%d")
    changelog = f"#### Release {args['version']} - {date_time} <p>\n"
    single_commits = get_commits(gl_project=gitlab_project, since=args['since'], until=args['until'])
    for commit in single_commits:
        if not commit.title.startswith('Merge branch'):
            message = commit.message.replace("\n", " ")
            changelog = changelog + f"** Commits into master: ** <p>\n" \
                                    f" - [{commit.short_id}]({commit.web_url}) " \
                                    f"{commit.title}  {message}\n"
    mrs = get_merge_requests_with_commits(gl_project=gitlab_project, since=args['since'], until=args['until'])
    for mr in mrs:
        changelog = changelog + f"\n**Merge Request**  [{mr.iid} - {mr.title}]({mr.web_url})<p>\n"
        if mr.description != '':
            description = mr.description.replace("\n", " ")
            changelog = changelog + f"**description** -- {description}<p>\n"
        changelog = changelog + "***Commits in mr :***\n"
        for commit in mr.commits():
            message = commit.message.replace("\n", " ")
            changelog = changelog + f" - [{commit.short_id}]({commit.web_url}) " \
                                    f" {commit.title} {message}\n"
    return changelog


def create_new_release(args, changelog):
    gl = gitlab.Gitlab(args['url'], private_token=args['token'])
    gitlab_project = gl.projects.get(args['project'])

    try:
        gitlab_project.releases.create({'tag_name': args['version'], 'ref': 'master', 'protected': True,
                                        'description': f"{changelog}"})
    except gitlab.exceptions.GitlabCreateError as ex:
        print('Gitlab : ', ex.response_body)
        print(ex.error_message)
    else:
        print(f" Release {args['version']} was successfully created")


def main():
    args = process_arguments()

    gl = gitlab.Gitlab(args['url'], private_token=args['token'])
    gitlab_project = gl.projects.get(args['project'])

    if args["since"] == "":
        gl_tag = gitlab_project.tags.list()[0]
        print(f"--since was not specified. Will be used tag {gl_tag.name}")
        args["since"] = gl_tag.commit['created_at']
    else:
        args["since"] = get_data_from_tag(gl_project=gitlab_project, tag=args["since"])

    if args["until"] != "":
        args["until"] = get_data_from_tag(gl_project=gitlab_project, tag=args["until"])

    if args["version"] == "":
        args["version"] = increment_version(args=args)
        print(f"--version was not specified. Will be used version {args['version']}")

    changelog = generate_changelog(args)

    create_new_release(args, changelog)


if __name__ == "__main__":
    main()
