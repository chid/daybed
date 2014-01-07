import os
import logging

from couchdb.client import Server
from couchdb.http import PreconditionFailed
from couchdb.design import ViewDefinition

from .views import docs
from .database import Database


logger = logging.getLogger(__name__)


class CouchDBBackend(object):
    def db(self):
        return Database(self.server[self.db_name], self._generate_id)

    def __init__(self, config):
        settings = config.registry.settings

        self.config = config
        self.server = Server(settings['backend.db_host'])
        self.db_name = os.environ.get('DB_NAME', settings['backend.db_name'])

        # model id generator
        generator = config.maybe_dotted(settings['daybed.id_generator'])
        self._generate_id = generator(config)

        self.create_db_if_not_exist()
        self.sync_views()

    def delete_db(self):
        del self.server[self.db_name]

    def create_db_if_not_exist(self):
        try:
            self.server.create(self.db_name)
            logger.debug('Creating and using db "%s"' % self.db_name)
        except PreconditionFailed:
            logger.debug('Using db "%s".' % self.db_name)

    def sync_views(self):
        ViewDefinition.sync_many(self.server[self.db_name], docs)
