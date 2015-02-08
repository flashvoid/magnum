#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""Magnum Kubernetes RPC handler."""

from oslo_config import cfg

from magnum.common import clients
from magnum.conductor.handlers.common import kube_utils
from magnum import objects
from magnum.openstack.common._i18n import _
from magnum.openstack.common import log as logging


LOG = logging.getLogger(__name__)


kubernetes_opts = [
    cfg.StrOpt('k8s_protocol',
               default='http',
               help=_('Default protocol of k8s master endpoint'
               ' (http or https).')),
    cfg.IntOpt('k8s_port',
               default=8080,
               help=_('Default port of the k8s master endpoint.')),
]

cfg.CONF.register_opts(kubernetes_opts, group='kubernetes')


def _retrieve_bay(ctxt, obj):
    bay_uuid = obj.bay_uuid
    return objects.Bay.get_by_uuid(ctxt, bay_uuid)


def _retrieve_baymodel(ctxt, obj):
    return objects.BayModel.get_by_uuid(ctxt, obj.baymodel_id)


def _retrieve_k8s_master_url(ctxt, obj):
    apiserver_port = cfg.CONF.kubernetes.k8s_port
    if hasattr(obj, 'bay_uuid'):
        obj = _retrieve_bay(ctxt, obj)

    baymodel = _retrieve_baymodel(ctxt, obj)
    if baymodel.apiserver_port is not None:
        apiserver_port = baymodel.apiserver_port

    params = {
        'k8s_protocol': cfg.CONF.kubernetes.k8s_protocol,
        'k8s_port': apiserver_port,
        'master_address': obj.master_address
    }
    return "%(k8s_protocol)s://%(master_address)s:%(k8s_port)s" % params


def _object_has_stack(ctxt, obj):
    osc = clients.OpenStackClients(ctxt)
    if hasattr(obj, 'bay_uuid'):
        obj = _retrieve_bay(ctxt, obj)

    stack = osc.heat().stacks.get(obj.stack_id)
    if (stack.stack_status == 'DELETE_COMPLETE' or
       stack.stack_status == 'DELETE_IN_PROGRESS'):
        return False
    else:
        return True


class Handler(object):
    """These are the backend operations.  They are executed by the backend
         service.  API calls via AMQP (within the ReST API) trigger the
         handlers to be called.

         This handler acts as an interface to executes kubectl command line
         services.
    """

    def __init__(self):
        super(Handler, self).__init__()
        self.kube_cli = kube_utils.KubeClient()

    def service_create(self, ctxt, service):
        LOG.debug("service_create")
        k8s_master_url = _retrieve_k8s_master_url(ctxt, service)
        # trigger a kubectl command
        status = self.kube_cli.service_create(k8s_master_url, service)
        if not status:
            return None
        # call the service object to persist in db
        service.create(ctxt)
        return service

    def service_update(self, ctxt, service):
        LOG.debug("service_update")
        # trigger a kubectl command
        status = self.kube_cli.service_update(service)
        if not status:
            return None
        # call the service object to persist in db
        service.refresh(ctxt)
        return service

    def service_list(self, ctxt):
        LOG.debug("service_list")
        return self.kube_cli.service_list()

    def service_delete(self, ctxt, uuid):
        LOG.debug("service_delete")
        service = objects.Service.get_by_uuid(ctxt, uuid)
        k8s_master_url = _retrieve_k8s_master_url(ctxt, service)
        if _object_has_stack(ctxt, service):
            # trigger a kubectl command
            status = self.kube_cli.service_delete(k8s_master_url, service.name)
            if not status:
                return None
        # call the service object to persist in db
        service.destroy(ctxt)

    def service_get(self, ctxt, uuid):
        LOG.debug("service_get")
        return self.kube_cli.service_get(uuid)

    def service_show(self, uuid):
        LOG.debug("service_show")
        return self.kube_cli.service_show(uuid)

    # Pod Operations
    def pod_create(self, ctxt, pod):
        LOG.debug("pod_create")
        k8s_master_url = _retrieve_k8s_master_url(ctxt, pod)
        # trigger a kubectl command
        status = self.kube_cli.pod_create(k8s_master_url, pod)
        # TODO(yuanying): Is this correct location of updating status?
        if not status:
            pod.status = 'failed'
        else:
            pod.status = 'pending'
        # call the pod object to persist in db
        # TODO(yuanying): parse pod file and,
        # - extract pod name and set it
        # - extract pod labels and set it
        # TODO(yuanying): Should kube_utils support definition_url?
        # When do we get pod labels and name?
        pod.create()
        return pod

    def pod_update(self, ctxt, pod):
        LOG.debug("pod_update")
        # trigger a kubectl command
        status = self.kube_cli.pod_update(pod)
        if not status:
            return None
        # call the pod object to persist in db
        pod.refresh(ctxt)
        return pod

    def pod_list(self, ctxt):
        LOG.debug("pod_list")
        return self.kube_cli.pod_list()

    def pod_delete(self, ctxt, uuid):
        LOG.debug("pod_delete ")
        # trigger a kubectl command
        pod = objects.Pod.get_by_uuid(ctxt, uuid)
        k8s_master_url = _retrieve_k8s_master_url(ctxt, pod)
        if _object_has_stack(ctxt, pod):
            status = self.kube_cli.pod_delete(k8s_master_url, pod.name)
            if not status:
                return None
        # call the pod object to persist in db
        pod.destroy(ctxt)

    def pod_get(self, ctxt, uuid):
        LOG.debug("pod_get")
        return self.kube_cli.pod_get(uuid)

    def pod_show(self, ctxt, uuid):
        LOG.debug("pod_show")
        return self.kube_cli.pod_show(uuid)

    # Replication Controller Operations
    def rc_create(self, ctxt, rc):
        LOG.debug("rc_create")
        k8s_master_url = _retrieve_k8s_master_url(ctxt, rc)
        # trigger a kubectl command
        status = self.kube_cli.rc_create(k8s_master_url, rc)
        if not status:
            return None
        # call the rc object to persist in db
        rc.create(ctxt)
        return rc

    def rc_update(self, ctxt, rc):
        LOG.debug("rc_update")
        # trigger a kubectl command
        status = self.kube_cli.rc_update(rc)
        if not status:
            return None
        # call the rc object to persist in db
        rc.refresh(ctxt)
        return rc

    def rc_delete(self, ctxt, uuid):
        LOG.debug("rc_delete ")
        rc = objects.ReplicationController.get_by_uuid(ctxt, uuid)
        k8s_master_url = _retrieve_k8s_master_url(ctxt, rc)
        if _object_has_stack(ctxt, rc):
            # trigger a kubectl command
            status = self.kube_cli.pod_delete(k8s_master_url, rc.name)
            if not status:
                return None
        # call the rc object to persist in db
        rc.destroy(ctxt)
