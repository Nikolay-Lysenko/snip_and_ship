"""
This script provides tools for updating SQLite database used by
Flask application.
This task is not done by pre-commit hook, because it is not a good
practice to store binary files in a Git repository and so
the file managed by the script differs from files managed by
pre-commit hook.

Author: Nikolay Lysenko
"""


import sqlite3
from collections import defaultdict
from typing import Dict, Any
from contextlib import contextmanager, closing

from readingbricks import utils


@contextmanager
def open_transaction(conn: sqlite3.Connection):
    """
    Open transaction to SQLite database within a context.
    """
    cur = conn.cursor()
    cur.execute('BEGIN TRANSACTION')
    try:
        yield cur
    except Exception as e:  # pragma: no cover
        print(e)
        cur.execute('ROLLBACK')
    else:
        cur.execute('COMMIT')
    finally:
        cur.close()


class DatabaseCreator:
    """
    Instances of this class can create SQLite database where tables
    represent tags and rows of a table represent notes tagged with
    the corresponding tag.

    :param path_to_ipynb_notes:
        path to directory where Jupyter files with notes are located
    :param path_to_db:
        path to SQLite database; if this file already exists, it will
        be overwritten, else the file will be created
    """

    def __init__(self, path_to_ipynb_notes: str, path_to_db: str):
        self.__path_to_ipynb_notes = path_to_ipynb_notes
        self.__path_to_db = path_to_db

    @staticmethod
    def __update_mapping_of_tags_to_notes(
            tag_to_notes: defaultdict,
            cell: Dict[str, Any]
            ) -> defaultdict:
        # Store cell header in lists that relates to its tags.
        cell_header = cell['source'][0].rstrip('\n')
        cell_header = cell_header.lstrip('## ')
        cell_tags = cell['metadata']['tags'] + ['all_notes']
        for tag in cell_tags:
            tag_to_notes[tag].append(cell_header)
        return tag_to_notes

    def __write_tag_to_notes_mapping_to_db(
            self,
            tag_to_notes: defaultdict
            ) -> type(None):
        # Write content of `tag_to_notes` to the target DB.
        with closing(sqlite3.connect(self.__path_to_db)) as conn:
            with open_transaction(conn) as cur:
                for k, v in tag_to_notes.items():
                    cur.execute(
                        f"CREATE TABLE IF NOT EXISTS {k} (note_id VARCHAR)"
                    )
                    cur.execute(
                        f"""
                        CREATE UNIQUE INDEX IF NOT EXISTS
                            {k}_index
                        ON
                            {k} (note_id)
                        """
                    )
                    cur.execute(
                        f"DELETE FROM {k}"
                    )
                    for note_title in v:
                        cur.execute(
                            f"INSERT INTO {k} (note_id) VALUES (?)",
                            (utils.compress(note_title),)
                        )
            with closing(conn.cursor()) as cur:
                cur.execute('VACUUM')

    def create_or_update_db(self) -> type(None):
        """
        Create SQLite database if it does not exist or update it else.

        :return:
            None
        """
        tag_to_notes = defaultdict(lambda: [])
        for cell in utils.extract_cells(self.__path_to_ipynb_notes):
            tag_to_notes = self.__update_mapping_of_tags_to_notes(
                tag_to_notes, cell
            )
        self.__write_tag_to_notes_mapping_to_db(tag_to_notes)
