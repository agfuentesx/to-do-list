import json
import psycopg2
import psycopg2.extras
import os

# Database configuration
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME', 'postgres')

def get_db_connection():
    """Create and return database connection"""
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return connection
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        raise e

def create_response(status_code, body):
    """Create standardized API response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }

def lambda_handler(event, context):
    """Main Lambda handler"""
    
    print(f"Event: {json.dumps(event)}")
    
    if event.get('httpMethod') == 'OPTIONS':
        return create_response(200, {'message': 'OK'})
    
    http_method = event.get('httpMethod')
    path_parameters = event.get('pathParameters') or {}
    todo_id = path_parameters.get('id')
    
    try:
        if http_method == 'GET' and not todo_id:
            return get_all_todos()
        
        elif http_method == 'GET' and todo_id:
            return get_todo_by_id(todo_id)
        
        elif http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            return create_todo(body)
        
        elif http_method == 'PUT' and todo_id:
            body = json.loads(event.get('body', '{}'))
            return update_todo(todo_id, body)
        
        elif http_method == 'DELETE' and todo_id:
            return delete_todo(todo_id)
        
        else:
            return create_response(400, {'error': 'Invalid request'})
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return create_response(500, {
            'error': 'Internal server error',
            'message': str(e)
        })

# ==================== CRUD OPERATIONS ====================

def get_all_todos():
    """GET /todos - Retrieve all todos"""
    connection = get_db_connection()
    
    try:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT id, title, description, completed, created_at, updated_at 
            FROM todos 
            ORDER BY created_at DESC
        """)
        todos = cursor.fetchall()
        
        return create_response(200, {
            'success': True,
            'count': len(todos),
            'data': todos
        })
        
    finally:
        cursor.close()
        connection.close()

def get_todo_by_id(todo_id):
    """GET /todos/{id} - Retrieve specific todo"""
    connection = get_db_connection()
    
    try:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT id, title, description, completed, created_at, updated_at 
            FROM todos 
            WHERE id = %s
        """, (todo_id,))
        todo = cursor.fetchone()
        
        if not todo:
            return create_response(404, {
                'success': False,
                'error': f'Todo with id {todo_id} not found'
            })
        
        return create_response(200, {
            'success': True,
            'data': todo
        })
        
    finally:
        cursor.close()
        connection.close()

def create_todo(body):
    """POST /todos - Create new todo"""
    
    if not body.get('title'):
        return create_response(400, {
            'success': False,
            'error': 'Title is required'
        })
    
    connection = get_db_connection()
    
    try:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            INSERT INTO todos (title, description, completed) 
            VALUES (%s, %s, %s)
            RETURNING id, title, description, completed, created_at, updated_at
        """, (
            body.get('title'),
            body.get('description', ''),
            body.get('completed', False)
        ))
        
        new_todo = cursor.fetchone()
        connection.commit()
        
        return create_response(201, {
            'success': True,
            'message': 'Todo created successfully',
            'data': new_todo
        })
        
    finally:
        cursor.close()
        connection.close()

def update_todo(todo_id, body):
    """PUT /todos/{id} - Update existing todo"""
    connection = get_db_connection()
    
    try:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if exists
        cursor.execute("SELECT id FROM todos WHERE id = %s", (todo_id,))
        if not cursor.fetchone():
            return create_response(404, {
                'success': False,
                'error': f'Todo with id {todo_id} not found'
            })
        
        # Build update
        update_fields = []
        values = []
        
        if 'title' in body:
            update_fields.append("title = %s")
            values.append(body['title'])
        
        if 'description' in body:
            update_fields.append("description = %s")
            values.append(body['description'])
        
        if 'completed' in body:
            update_fields.append("completed = %s")
            values.append(body['completed'])
        
        if not update_fields:
            return create_response(400, {
                'success': False,
                'error': 'No fields to update'
            })
        
        update_fields.append("updated_at = NOW()")
        values.append(todo_id)
        
        sql = f"""
            UPDATE todos 
            SET {', '.join(update_fields)} 
            WHERE id = %s
            RETURNING id, title, description, completed, created_at, updated_at
        """
        
        cursor.execute(sql, values)
        updated_todo = cursor.fetchone()
        connection.commit()
        
        return create_response(200, {
            'success': True,
            'message': 'Todo updated successfully',
            'data': updated_todo
        })
        
    finally:
        cursor.close()
        connection.close()

def delete_todo(todo_id):
    """DELETE /todos/{id} - Delete todo"""
    connection = get_db_connection()
    
    try:
        cursor = connection.cursor()
        
        cursor.execute("SELECT id FROM todos WHERE id = %s", (todo_id,))
        if not cursor.fetchone():
            return create_response(404, {
                'success': False,
                'error': f'Todo with id {todo_id} not found'
            })
        
        cursor.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
        connection.commit()
        
        return create_response(200, {
            'success': True,
            'message': f'Todo with id {todo_id} deleted successfully'
        })
        
    finally:
        cursor.close()
        connection.close()
