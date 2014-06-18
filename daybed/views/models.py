from six import iteritems
from collections import defaultdict
from cornice import Service
from pyramid.security import Everyone

from daybed.permissions import (
    get_model_permissions, invert_permissions_matrix,
    dict_list2set, dict_set2list, PERMISSIONS_SET
)
from daybed.backends.exceptions import ModelNotFound
from daybed.views.errors import forbidden_view
from daybed.schemas.validators import model_validator, permissions_validator
from daybed.events import ModelCreated, ModelDeleted


models = Service(name='models', path='/models', description='Models')


model = Service(name='model',
                path='/models/{model_id}',
                description='Model',
                renderer="jsonp",
                cors_origins=('*',))


definition = Service(name='model-definition',
                     path='/models/{model_id}/definition',
                     description='Model Definitions',
                     renderer="jsonp",
                     cors_origins=('*',))


permissions = Service(name='model-permissions',
                      path='/models/{model_id}/permissions',
                      description='Model permissions',
                      renderer="jsonp",
                      cors_origins=('*',))


@definition.get(permission='get_definition')
def get_definition(request):
    """Retrieves a model definition."""
    model_id = request.matchdict['model_id']
    try:
        return request.db.get_model_definition(model_id)
    except ModelNotFound:
        request.errors.add('path', model_id, "model not found")
        request.errors.status = "404 Not Found"


@permissions.get(permission='get_permissions')
def get_permissions(request):
    """Retrieves a model permissions."""
    model_id = request.matchdict['model_id']
    try:
        permissions = request.db.get_model_permissions(model_id)
        return invert_permissions_matrix(permissions)
    except ModelNotFound:
        request.errors.add('path', model_id, "model not found")
        request.errors.status = "404 Not Found"


@permissions.patch(permission='put_permissions',
                   validators=(permissions_validator,))
def patch_permissions(request):
    """Update a model permissions."""
    model_id = request.matchdict['model_id']
    definition = request.db.get_model_definition(model_id)
    permissions = dict_list2set(request.db.get_model_permissions(model_id))

    for token, perms in iteritems(request.validated['permissions']):
        # Handle remove all
        if '-all' in [perm.lower() for perm in perms]:
            for perm in PERMISSIONS_SET:
                permissions[perm].discard(token)
        # Handle add all
        elif 'all' in [perm.lstrip('+').lower() for perm in perms]:
            for perm in PERMISSIONS_SET:
                permissions[perm].add(token)
        # Handle add/remove perms list
        else:
            for perm in perms:
                perm = perm.lower()
                if perm.startswith('-'):
                    permissions[perm.lstrip('-')].discard(token)
                else:
                    permissions[perm.lstrip('+')].add(token)

    request.db.put_model(definition, dict_set2list(permissions), model_id)
    return invert_permissions_matrix(permissions)


@permissions.put(permission='put_permissions',
                 validators=(permissions_validator,))
def put_permissions(request):
    """Update a model permissions."""
    model_id = request.matchdict['model_id']
    definition = request.db.get_model_definition(model_id)
    permissions = defaultdict(set)
    for token, perms in iteritems(request.validated['permissions']):
        perms = [p.lstrip('+').lower() for p in perms]
        if 'all' in perms:
            perms = PERMISSIONS_SET
        for perm in perms:
            if not perm.startswith('-'):
                permissions[perm].add(token)
    permissions = dict_set2list(permissions)
    request.db.put_model(definition, permissions, model_id)
    return invert_permissions_matrix(permissions)


@models.post(permission='post_model', validators=(model_validator,))
def post_models(request):
    """Creates a model with the given definition and records, if any."""
    if request.token:
        token = request.token
    else:
        token = Everyone

    model_id = request.db.put_model(
        definition=request.validated['definition'],
        permissions=get_model_permissions(token))

    event = ModelCreated(model_id, request)
    request.registry.notify(event)

    for record in request.validated['records']:
        request.db.put_record(model_id, record, [token])

    request.response.status = "201 Created"
    location = '%s/models/%s' % (request.application_url, model_id)
    request.response.headers['location'] = str(location)
    return {'id': model_id}


@model.delete(permission='delete_model')
def delete_model(request):
    """Deletes a model and its records."""
    model_id = request.matchdict['model_id']
    try:
        model = request.db.delete_model(model_id)
    except ModelNotFound:
        request.errors.status = "404 Not Found"
        request.errors.add('path', model_id, "model not found")
        return

    event = ModelDeleted(model_id, request)
    request.registry.notify(event)

    model["permissions"] = invert_permissions_matrix(model["permissions"])
    return model


@model.get(permission='get_model')
def get_model(request):
    """Retrieves the full model, definition and records."""
    model_id = request.matchdict['model_id']
    try:
        definition = request.db.get_model_definition(model_id),
    except ModelNotFound:
        request.errors.add('path', model_id, "model not found")
        request.errors.status = "404 Not Found"
        return

    if "read_all_records" not in request.permissions:
        records = request.db.get_records_with_authors(model_id)
        records = [r["record"] for r in records
                   if set(request.principals).intersection(r["authors"])]
    else:
        records = request.db.get_records(model_id)

    permissions = request.db.get_model_permissions(model_id)
    return {'definition': definition,
            'records': records,
            'permissions': invert_permissions_matrix(permissions)}


@model.put(validators=(model_validator,), permission='post_model')
def put_model(request):
    model_id = request.matchdict['model_id']

    try:
        request.db.get_model_definition(model_id)

        if request.has_permission('put_model'):
            try:
                request.db.delete_model(model_id)

                event = ModelDeleted(model_id, request)
                request.registry.notify(event)

            except ModelNotFound:
                pass
            return handle_put_model(request)
    except ModelNotFound:
        return handle_put_model(request)

    return forbidden_view(request)


def handle_put_model(request):
    model_id = request.matchdict['model_id']

    if request.token:
        token = request.token
    else:
        token = Everyone

    request.db.put_model(request.validated['definition'],
                         get_model_permissions(token),
                         model_id)

    event = ModelCreated(model_id, request)
    request.registry.notify(event)

    for record in request.validated['records']:
        request.db.put_record(model_id, record, [token])

    return {"id": model_id}
