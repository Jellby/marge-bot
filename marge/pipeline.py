from . import gitlab


GET, POST = gitlab.GET, gitlab.POST


class Pipeline(gitlab.Resource):
    def __init__(self, api, info, project_id):
        info['project_id'] = project_id
        super().__init__(api, info)

    @classmethod
    def pipelines_by_branch(
            cls, project_id, branch, api, *,
            ref=None,
            status=None,
            order_by='id',
            sort='desc',
    ):
        params = {
            'ref': branch if ref is None else ref,
            'order_by': order_by,
            'sort': sort,
        }
        if status is not None:
            params['status'] = status
        pipelines_info = api.call(GET(
            '/projects/{project_id}/pipelines'.format(project_id=project_id),
            params,
        ))

        return [cls(api, pipeline_info, project_id) for pipeline_info in pipelines_info]

    @classmethod
    def pipelines_by_merge_request(cls, project_id, merge_request_iid, api):
        """Fetch all pipelines for a merge request in descending order of pipeline ID."""
        # this API cannot be trusted yet
        #pipelines_info = api.call(GET(
        #    '/projects/{project_id}/merge_requests/{merge_request_iid}/pipelines'.format(
        #        project_id=project_id, merge_request_iid=merge_request_iid,
        #    )
        #))
        pipelines_info = api.call(GET(
            '/projects/{project_id}/pipelines'.format(
                project_id=project_id, merge_request_iid=merge_request_iid,
            ),
            {
                'ref': 'refs/merge-requests/{}/head'.format(merge_request_iid),
            }
        ))
        pipelines_info.sort(key=lambda pipeline_info: pipeline_info['id'], reverse=True)
        pipelines_info.sort(key=lambda pipeline_info:
            0 if pipeline_info['ref'].startswith('ref/merge_requests') else 1)
        return [cls(api, pipeline_info, project_id) for pipeline_info in pipelines_info]

    @classmethod
    def create(cls, project_id, ref, merge_request, api):
        try:
            pipeline_info = {}
            if ((merge_request.source_project_id == project_id) and
                (merge_request.source_branch == ref)):
                api.call(POST(
                    '/projects/{project_id}/merge_requests/{mr_id}/pipelines'.format(
                        project_id=project_id,
                        mr_id=merge_request.iid,
                    )),
                    response_json=pipeline_info
                )
            else:
                api.call(POST(
                    '/projects/{project_id}/pipeline'.format(project_id=project_id), {'ref': ref}),
                    response_json=pipeline_info
                )
            return cls(api, pipeline_info, project_id)
        except gitlab.ApiError:
            return None

    @property
    def project_id(self):
        return self.info['project_id']

    @property
    def id(self):
        return self.info['id']

    @property
    def status(self):
        return self.info['status']

    @property
    def ref(self):
        return self.info['ref']

    @property
    def sha(self):
        return self.info['sha']

    def cancel(self):
        return self._api.call(POST(
            '/projects/{0.project_id}/pipelines/{0.id}/cancel'.format(self),
        ))

    def get_jobs(self):
        jobs_info = self._api.call(GET(
            '/projects/{0.project_id}/pipelines/{0.id}/jobs'.format(self),
        ))

        return jobs_info
