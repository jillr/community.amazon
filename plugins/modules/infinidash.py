#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
module: infinidash
short_description: Create and delete AWS Infinidash Dashes.
version_added: 2.0.0
description:
  - Creates AWS Infinidashes
  - Deletes AWS Infinidashes
requirements: [ boto3 ]
options:
  name:
    description:
      - Name to give the Dash
    type: str
  dash_id:
    description:
      - Required when deleting a Dash
    type: str
  dash_config:
    description:
      - A properly formatted json policy as string, see
        U(https://github.com/ansible/ansible/issues/7005#issuecomment-42894813).
        Cannot be used with I(config_file).
      - Option when creating a dash. If not provided AWS will
        utilise a default policy which provides full access to the service.
    required: false
    type: json
  config_file:
    description:
      - The path to the properly json formatted config file, see
        U(https://github.com/ansible/ansible/issues/7005#issuecomment-42894813)
        on how to use it properly. Cannot be used with I(dash_config).
      - Option when creating a dash. If not provided AWS will
        utilise a default policy which provides full access to the service.
    required: false
    type: path    
  state:
    description:
        - present to ensure resource is created.
        - absent to remove resource
    required: false
    default: present
    choices: [ "present", "absent" ]
    type: str
  tags:
    description:
      - A dict of tags to apply to the internet gateway.
      - To remove all tags set I(tags={}) and I(purge_tags=true).
    type: dict
  wait:
    description:
      - Wait for Dash to be in an available state before returning.
    type: bool
    default: true
  wait_timeout:
    description:
      - Used in conjunction with wait. Number of seconds to wait for status.
        Unfortunately this is ignored for delete actions due to a difference in
        behaviour from AWS.
    required: false
    default: 320
    type: int
'''

EXAMPLES = r'''
# Note: These examples do not set authentication details, see the AWS Guide for details.

- name: Create new Dash
  community.aws.infinidash:
    state: present
    region: us-east-1
    name: InfinidashRawks
    policy_file: "{{ role_path }}/files/dash_config.json"
  register: new_dash
'''

RETURN = r'''
id:
  description: The Amazon Resource Name of the dash.
  returned: when I(state=present)
  type: str
  sample: arn:aws:dash:us-east-1:148830907657:infiniDash:888d9b58-d93a-40c4-90cf-759197a2621a:dashName/InfinidashRawks
changed:
  description: Whether the state of the dash has changed.
  returned: always
  type: bool
  sample: false
created_time:
  description: The creation date and time for the dash.
  returned: when I(state=present)
  type: str
  sample: '2017-11-03 23:46:44.841000'
config:
  description: the dash configuration as returned by boto3
  returned: when I(state=present)
  type: dict   
'''

import json
import traceback

try:
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    pass  # protected by AnsibleAWSModule

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.core import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.ec2 import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.ec2 import ensure_tags


def create_dash(client, module, config):
    changed = False
    if module.params.get('dash_id'):
        try:
            dash = client.describe_dashes(aws_retry=True, DashIds=[module.params.get('dash_id')])
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg="Failed to describe dash ID {}".format(module.params.get('dash_id')))

    if dash:
        # Already exists, return
        module.exit_json(changed, dash)
    else:
        try:
            changed = True
            dash = client.create_dash(aws_retry=True, DashName=module.params.get('name'), DashConfig=config)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg="Dash creation failed!")

        # TODO: tags and compare config for changes
        module.exit_json(changed, dash)

def remove_dash(client, module):
    changed = True
    try:
        client.delete_dash(aws_retry=True, DashId=module.params.get('dash_id'))
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg="Failed to delete dash ID {}".format(module.params.get('dash_id'))
    module.exit_json(changed, dash=None)


def main():
    argument_spec = dict(
        name=dict(required=True),
        dash_config=dict(type='json'),
        config_file=dict(type='path'),
        state=dict(default='present', choices=['present', 'absent']),
        tags=dict(type='dict'),
        wait=dict(type='bool', default=False),
        wait_timeout=dict(type='int', default=320, required=False),
    )
    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[['policy', 'policy_file']],
    )

    state=module.params.get('state')
    client = module.client('dash', retry_decorator=AWSRetry.jittered_backoff())

    # Ensure dash is present
    if state == 'present':
        config = None
        if module.params.get('dash_config'):
            try:
                config = json.loads(module.params.get('policy'))
            except ValueError as e:
                module.fail_json(msg=str(e), exception=traceback.format_exc(),
                                 **camel_dict_to_snake_dict(e.response))

        elif module.params.get('config_file'):
            try:
                with open(module.params.get('config_file'), 'r') as json_data:
                    config = json.load(json_data)
            except Exception as e:
                module.fail_json(msg=str(e), exception=traceback.format_exc(),
                                 **camel_dict_to_snake_dict(e.response))
        create_dash(client, module, config)
    else:
       remove_dash(client, module)