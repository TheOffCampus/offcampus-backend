from flask import Flask, request, jsonify
from supabase import create_client, Client

app = Flask(__name__)

SUPABASE_URL='https://ihnradjuxnddmmioyeqp.supabase.co/'
SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlobnJhZGp1eG5kZG1taW95ZXFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDc5NDkyODcsImV4cCI6MjAyMzUyNTI4N30.cebjm2GbItaRLa81OYTi3Suffy8u52hO3lSRgjrK5r8'

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_rec_from_prefs(prefs):
    rent = prefs["rent"]
    campus = prefs["campus"]
    sqft = prefs["sqft"]

    query = f"""
        SELECT
            id AS property_id,
            data AS property_data,
            rental_object
        FROM (
            SELECT
                id,
                data,
                jsonb_array_elements(data->'rentals') AS rental_object
            FROM properties
        ) AS rentals
        WHERE (rental_object->>'rent')::int <= {rent}
        AND (rental_object->>'squareFeet')::int >= {sqft};
    """

    result = supabase.sql(query).execute()

    return result

# Execute the raw SQL query

@app.route('/get_recommendations', methods=['GET'])
def hello_world():
    id = request.headers.get('id')

    if not id:
        return jsonify({'error': 'Missing id header'}), 400
    
    try:
        data = supabase.table('User').select('*').eq('uuid', uuid).execute()

        if data.data:
            return jsonify(data.data), 200
        else:
            return jsonify({'error': 'User not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

