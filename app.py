from flask import Flask, request, jsonify
from supabase import create_client, Client

app = Flask(__name__)

SUPABASE_URL='https://ihnradjuxnddmmioyeqp.supabase.co/'
SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlobnJhZGp1eG5kZG1taW95ZXFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDc5NDkyODcsImV4cCI6MjAyMzUyNTI4N30.cebjm2GbItaRLa81OYTi3Suffy8u52hO3lSRgjrK5r8'

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_recs_query(prefs):
    query = f"""
        SELECT
            p.id AS property_id,
            p.data AS property_data,
            rental_object,
            (
                ({ prefs["miles_weight"] } * 1000 * (c.college->>'miles')::float) +
                ({ prefs["sqft_weight"] } * 800 * (rental_object->>'squareFeet')::int) +
                ({ prefs["rent_weight"] } * (rental_object->>'rent')::int)
            ) AS weighted_score
        FROM
            properties p,
            jsonb_array_elements(p.data->'schools'->'colleges') AS c(college)
        CROSS JOIN LATERAL
            jsonb_array_elements(p.data->'rentals') AS rental_object
        WHERE
            c.college @> '{"name": "{ prefs["campus"] or "Texas A&M University" }"}'
            AND (rental_object->>'rent')::int <= { prefs["max_rent"] or 5000 }
            AND (rental_object->>'squareFeet')::int >= { prefs["min_sqft"] or 0 }]
        ORDER BY weighted_score ASC
        LIMIT 50
        OFFSET ({ prefs["page"] } - 1) * 50;
    """

    result = supabase.sql(query).execute()

    return result.data

def get_prefs_query(id):
    result = supabase.table("User").select("preferences").eq("id", id).execute()

    preferences = result.data[0]['preferences']

    return preferences

print(get_recs_query(get_prefs_query(5)))
# Execute the raw SQL query
@app.route('/get_recommendations', methods=['GET'])
def get_recs_api():
    id = request.headers.get('id')

    if not id:
        return jsonify({'error': 'Missing id header'}), 400
    
    try:
        prefs = get_prefs_query()
        recs = get_recs_query(prefs)

        return recs
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

