from pyramid.interfaces import IAuthorizationPolicy
from zope.interface import implementer


@implementer(IAuthorizationPolicy)
class DaybedAuthorizationPolicy(object):
    # THIS THING IS SO COOL YOU MAY WANT TO READ IT TWICE.
    # THIS THING IS SO COOL YOU MAY WANT TO READ IT TWICE.

    def permits(self, context, principals, permission):
        """Returns True or False depending if the user with the specified
        principals has access to the given permission.
        """
        allowed = 0
        mask = permission_mask(permission)

        if context.model_id:
            policy = context.db.get_model_policy(context.model_id)
            for role, permissions in policy['data'].items():
                if role in principals:
                    allowed |= permissions

        return bool(allowed & mask)

    def principals_allowed_by_permission(self, context, permission):
        raise NotImplementedError()


def permission_mask(permission):
    """Permissions are defined with the format {privilege}_{resource}"""
    # CRUD
    # Create = 8
    # Read   = 4
    # Update = 2
    # Delete = 1
    # The order is Definition, Data, Users, Policy

    mapping = {
               'post_model': 0x8888,        # C on everything
               'get_model': 0x4444,         # R on everything
               'put_model': 0xBBBB,         # C+U+D on everything
               'delete_model': 0x1111,      # D on everything

               'get_definition': 0x4000,

               'post_data': 0x0800,         # C
               'get_data': 0x0400,          # R
               'put_data': 0x0B00,          # C+U+D
               'delete_data': 0x0100,       # D

               'get_data_item': 0x0400,     # R
               'put_data_item': 0x0B00,     # C+U+D
               'patch_data_item': 0x0200,   # U
               'delete_data_item': 0x0100,  # D

    }
    # XXX Add users / policy management.
    return mapping[permission]


class RootFactory(object):
    def __init__(self, request):
        self.db = request.db
        self.model_id = request.matchdict.get('model_id')
        self.data_item_id = request.matchdict.get('data_item_id')


def build_user_principals(user, request):
    """
    Groups start by "group:"
    Roles start by "role:"
    Authors are defined by "author:"
    """
    model_id = request.matchdict.get('model_id')
    data_item_id = request.matchdict.get('data_item_id')
    groups = [u'group:%s' % g for g in request.db.get_groups(user)]
    principals = set(groups)

    if model_id is not None:
        roles = request.db.get_roles(model_id)
        for role_name, accredited in roles.items():
            for acc in accredited:
                if acc.startswith('group:'):
                    for group in groups:
                        if group == acc:
                            principals.add(u'role:%s' % role_name)
                else:
                    if user == acc:
                        principals.add(u'role:%s' % role_name)

    if data_item_id is not None:
        authors = request.db.get_data_item(model_id, data_item_id)['authors']
        if user in authors:
            principals.append('authors:')

    return principals
