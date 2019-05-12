import logging as log
from . import gitlab
from .approvals import Approvals


GET, POST, PUT, DELETE = gitlab.GET, gitlab.POST, gitlab.PUT, gitlab.DELETE


class MergeRequest(gitlab.Resource):

    @classmethod
    def create(cls, api, project_id, params):
        merge_request_info = api.call(POST(
            '/projects/{project_id}/merge_requests'.format(project_id=project_id),
            params,
        ))
        merge_request = cls(api, merge_request_info)
        return merge_request

    @classmethod
    def search(cls, api, project_id, params):
        merge_requests = api.collect_all_pages(GET(
            '/projects/{project_id}/merge_requests'.format(project_id=project_id),
            params,
        ))
        return [cls(api, merge_request) for merge_request in merge_requests]

    @classmethod
    def fetch_by_iid(cls, project_id, merge_request_iid, api):
        merge_request = cls(api, {'iid': merge_request_iid, 'project_id': project_id})
        merge_request.refetch_info()
        return merge_request

    @classmethod
    def fetch_all_open_for_user(cls, project_id, user_id, api):
        try:
            all_merge_request_infos = api.collect_all_pages(GET(
                '/projects/{project_id}/merge_requests'.format(project_id=project_id),
                {'state': 'opened', 'order_by': 'created_at', 'sort': 'asc'},
            ))
        except (gitlab.InternalServerError, gitlab.TooManyRequests):
            log.warning('Internal server error from GitLab! Ignoring...')
            all_merge_request_infos = []
        my_merge_request_infos = [
            mri for mri in all_merge_request_infos
            if user_id in [mra.get('id') for mra in mri['assignees']]
        ]

        return [cls(api, merge_request_info) for merge_request_info in my_merge_request_infos]

    @property
    def project_id(self):
        return self.info['project_id']

    @property
    def iid(self):
        return self.info['iid']

    @property
    def title(self):
        return self.info['title']

    @property
    def state(self):
        return self.info['state']

    @property
    def assignee_id(self):
        assignee = self.info['assignee'] or {}
        return assignee.get('id')

    @property
    def assignee_ids(self):
        assignees = self.info['assignees'] or []
        return [a.get('id') for a in assignees]

    @property
    def author_id(self):
        return self.info['author'].get('id')

    @property
    def source_branch(self):
        return self.info['source_branch']

    @property
    def target_branch(self):
        return self.info['target_branch']

    @property
    def sha(self):
        return self.info['sha']

    @property
    def squash(self):
        return self.info.get('squash', False)  # missing means auto-squash not supported

    @property
    def source_project_id(self):
        return self.info['source_project_id']

    @property
    def target_project_id(self):
        return self.info['target_project_id']

    @property
    def work_in_progress(self):
        return self.info['work_in_progress']

    @property
    def approved_by(self):
        return self.info['approved_by']

    @property
    def web_url(self):
        return self.info['web_url']

    def refetch_info(self):
        self._info = self._api.call(GET('/projects/{0.project_id}/merge_requests/{0.iid}'.format(self)))

    def comment(self, message):
        if self._api.version().release >= (9, 2, 2):
            notes_url = '/projects/{0.project_id}/merge_requests/{0.iid}/notes'.format(self)
        else:
            # GitLab botched the v4 api before 9.2.2
            notes_url = '/projects/{0.project_id}/merge_requests/{0.id}/notes'.format(self)

        return self._api.call(POST(notes_url, {'body': message}))

    def accept(self, remove_branch=False, sha=None):
        return self._api.call(PUT(
            '/projects/{0.project_id}/merge_requests/{0.iid}/merge'.format(self),
            dict(
                should_remove_source_branch=remove_branch,
                merge_when_pipeline_succeeds=True,
                sha=sha or self.sha,  # if provided, ensures what is merged is what we want (or fails)
            ),
        ))

    def close(self):
        return self._api.call(PUT(
            '/projects/{0.project_id}/merge_requests/{0.iid}'.format(self),
            {'state_event': 'close'},
        ))

    def assign_to(self, user_ids):
        return self._api.call(PUT(
            '/projects/{0.project_id}/merge_requests/{0.iid}'.format(self),
            {'assignee_ids': user_ids},
        ))

    def unassign(self, user_id):
        assignees = [x for x in merge_request.assignee_ids if x != user_id]
        return self.assign_to(assignees)

    def fetch_approvals(self):
        # 'id' needed for for GitLab 9.2.2 hack (see Approvals.refetch_info())
        info = {'id': self.id, 'iid': self.iid, 'project_id': self.project_id}
        approvals = Approvals(self.api, info)
        approvals.refetch_info()
        return approvals

    def triggered(self, user_id):
        if self._api.version().release >= (9, 2, 2):
            notes_url = '/projects/{0.project_id}/merge_requests/{0.iid}/notes'.format(self)
        else:
            # GitLab botched the v4 api before 9.2.2
            notes_url = '/projects/{0.project_id}/merge_requests/{0.id}/notes'.format(self)

        comments = self._api.collect_all_pages(GET(notes_url))
        message = 'I created a new pipeline for [{sha:.8s}]'.format(sha=self.sha)
        my_comments = [c['body'] for c in comments if c['author']['id'] == user_id]
        return any(message in c for c in my_comments)

    def is_assigned_to(self, user_id):
        if self.assignee_id == user_id:
            return True
        if user_id in self.assignee_ids:
            return True
        return False
