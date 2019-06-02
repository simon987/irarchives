import sqlite3

from common import logger


class DB:
    """
    Database object.
    Used for communicating with the SQLite database.
    """

    def __init__(self, db_file, **schemas):
        """
        Initializes database.
        Attempts to creates tables with schemas if needed.
            * db_file - Name of the database file.
            * schemas - A python dictionary where:
                KEY is the table name,
                VALUE is that table's schema.

        For example:
            db = DB('file.db', {
                'Customer': 'name text, phone int, address text',
                'Order':    'id int primary key, customer_name text, cost real'})
            # This would open the 'file.db' file and create two tables with the respective schemas.
            If the tables already exist, the existing tables remain unaltered.
        """
        self.db_file = db_file

        # Don't create tables if not supplied.
        if schemas is not None and schemas != {} and schemas:

            # Create table for every schema given.
            for key in schemas:
                self.create_table(key, schemas[key])

    def create_table(self, table_name, schema):
        """Creates new table with schema"""
        with sqlite3.connect(self.db_file, timeout=10000) as conn:
            cur = conn.cursor()
            try:
                cur.execute('''CREATE TABLE IF NOT EXISTS %s (%s)''' % (table_name, schema))
                conn.commit()
            except sqlite3.OperationalError as e:
                # Ignore if table already exists, otherwise print error
                if str(e).find('already exists') == -1:
                    logger.error(e)

    def insert(self, table, values):
        """
        Inserts tuple of values into database.
            * table - The table name, a string
            * values - The tuple to insert into the database.

        Returns row id of tuple inserted, or -1 if error occurred.
        """
        with sqlite3.connect(self.db_file, timeout=10000) as conn:
            cur = conn.cursor()
            try:
                questions = ''
                for i in range(0, len(values)):
                    if questions != '':
                        questions += ','
                    questions += '?'
                exec_string = '''insert into %s values (%s)''' % (table, questions)
                cur.execute(exec_string, values)
                conn.commit()
                last_row_id = cur.lastrowid
                return last_row_id
            except sqlite3.IntegrityError:
                return -1

    def count(self, table, where):
        """
        Counts the number of tuples in 'table' where the 'where' condition holds
            * table - The table name, a string
            * where - A condition, such as "year == 1999"

        Returns # of tuples found in query.
        """
        with sqlite3.connect(self.db_file, timeout=10000) as conn:
            cur = conn.cursor()
            result = cur.execute('''select count(*) from %s where %s''' % (table, where,)).fetchall()
            return result[0][0]

    def select(self, what, table, where=''):
        """
        Executes a SQL SELECT command. Returns tuples
        Type the entire SELECT statement.
        For example:

            db = DB('file.db', {'table_name': 'id int primary key'} )
            tuples = db.select('''SELECT * FROM table WHERE id > 0''')
            for result in tuples:
                print result[0] # prints first attribute
                print result[1] # prints second attribute
                ...
        """
        with sqlite3.connect(self.db_file, timeout=10000) as conn:
            cur = conn.cursor()
            query_string = '''SELECT %s FROM %s''' % (what, table)
            if where != '':
                query_string += ''' WHERE %s''' % (where,)
            cur.execute(query_string)
            results = []
            for result in cur:
                results.append(result)
            return results

    def execute(self, statement):
        """
        Executes a statement. Similar to the 'select' method, but does not return anything.
        """
        with sqlite3.connect(self.db_file, timeout=10000) as conn:
            cur = conn.cursor()
            result = cur.execute(statement)
            conn.commit()
        return result
