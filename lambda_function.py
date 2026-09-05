import json
import pymysql
import os
import base64

# Database configuration from environment variables
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

def get_db_connection():
    """Create database connection"""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def create_response(status_code, body):
    """Create API response"""
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
    """Main handler"""
    
    print(f"Event received: {json.dumps(event)}")
    
    # Works for both HTTP API (v2) and REST API (v1) event formats
    http_method = (
        event.get('httpMethod')
        or event.get('requestContext', {}).get('http', {}).get('method')
    )
    path_parameters = event.get('pathParameters') or {}
    todo_id = path_parameters.get('id')
    
    # Handle CORS preflight
    if http_method == 'OPTIONS':
        return create_response(200, {'message': 'OK'})
    
    try:
        # Parse body (handle Base64 encoding)
        body = None
        if event.get('body'):
            body_content = event['body']
            
            # Decode if Base64 encoded
            if event.get('isBase64Encoded', False):
                body_content = base64.b64decode(body_content).decode('utf-8')
            
            # Parse JSON
            if body_content:
                try:
                    body = json.loads(body_content)
                except json.JSONDecodeError:
                    body = {}
        
        # Route requests
        if http_method == 'GET' and not todo_id:
            return get_all_todos()
        
        elif http_method == 'GET' and todo_id:
            return get_todo_by_id(todo_id)
        
        elif http_method == 'POST':
            return create_todo(body or {})
        
        elif http_method == 'PUT' and todo_id:
            return update_todo(todo_id, body or {})
        
        elif http_method == 'DELETE' and todo_id:
            return delete_todo(todo_id)
        
        else:
            return create_response(400, {
                'success': False,
                'error': f'Invalid request - Method: {http_method}'
            })
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, {
            'success': False,
            'error': 'Internal server error',
            'message': str(e)
        })

# ==================== CRUD OPERATIONS ====================

def get_all_todos():
    """GET /todos - Get all todos"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM todos ORDER BY created_at DESC")
            todos = cursor.fetchall()
            return create_response(200, {
                'success': True,
                'count': len(todos),
                'data': todos
            })
    finally:
        conn.close()

def get_todo_by_id(todo_id):
    """GET /todos/{id} - Get specific todo"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM todos WHERE id = %s", (todo_id,))
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
        conn.close()

def create_todo(body):
    """POST /todos - Create new todo"""
    
    if not body.get('title'):
        return create_response(400, {
            'success': False,
            'error': 'Title is required'
        })
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO todos (title, description, completed) VALUES (%s, %s, %s)",
                (body.get('title'), body.get('description', ''), body.get('completed', False))
            )
            conn.commit()
            
            todo_id = cursor.lastrowid
            cursor.execute("SELECT * FROM todos WHERE id = %s", (todo_id,))
            new_todo = cursor.fetchone()
            
            return create_response(201, {
                'success': True,
                'message': 'Todo created successfully',
                'data': new_todo
            })
    finally:
        conn.close()

def update_todo(todo_id, body):
    """PUT /todos/{id} - Update todo"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if exists
            cursor.execute("SELECT id FROM todos WHERE id = %s", (todo_id,))
            if not cursor.fetchone():
                return create_response(404, {
                    'success': False,
                    'error': f'Todo with id {todo_id} not found'
                })
            
            # Build update query
            updates = []
            values = []
            
            if 'title' in body:
                updates.append("title = %s")
                values.append(body['title'])
            
            if 'description' in body:
                updates.append("description = %s")
                values.append(body['description'])
            
            if 'completed' in body:
                updates.append("completed = %s")
                values.append(body['completed'])
            
            if not updates:
                return create_response(400, {
                    'success': False,
                    'error': 'No fields to update'
                })
            
            updates.append("updated_at = NOW()")
            values.append(todo_id)
            
            sql = f"UPDATE todos SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(sql, values)
            conn.commit()
            
            # Get updated todo
            cursor.execute("SELECT * FROM todos WHERE id = %s", (todo_id,))
            updated_todo = cursor.fetchone()
            
            return create_response(200, {
                'success': True,
                'message': 'Todo updated successfully',
                'data': updated_todo
            })
    finally:
        conn.close()

def delete_todo(todo_id):
    """DELETE /todos/{id} - Delete todo"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM todos WHERE id = %s", (todo_id,))
            if not cursor.fetchone():
                return create_response(404, {
                    'success': False,
                    'error': f'Todo with id {todo_id} not found'
                })
            
            cursor.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
            conn.commit()
            
            return create_response(200, {
                'success': True,
                'message': f'Todo with id {todo_id} deleted successfully'
            })
    finally:
        conn.close()