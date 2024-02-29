from flask import Flask, request, jsonify
from supabase import create_client, Client
from sqlalchemy import create_engine, text


app = Flask(__name__)

SUPABASE_URL='https://ihnradjuxnddmmioyeqp.supabase.co/'
SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlobnJhZGp1eG5kZG1taW95ZXFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDc5NDkyODcsImV4cCI6MjAyMzUyNTI4N30.cebjm2GbItaRLa81OYTi3Suffy8u52hO3lSRgjrK5r8'
SQLALCHEMY_DATABASE_URL = "postgresql://postgres.ihnradjuxnddmmioyeqp:oMbKlcQqT9APDtKG@aws-0-us-west-1.pooler.supabase.com/postgres"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def get_recs_query(prefs):
    query = text(f'''
        SELECT
            p.id AS property_id,
            p.data AS property_data,
            rental_object,
            (
                ({prefs.get("miles_weight")} * -1 * 1000 * (c.college->>'miles')::float) +
                ({prefs.get("sqft_weight")} * 1 * 800 * (rental_object->>'squareFeet')::int) +
                ({prefs.get("rent_weight")} * -1 * (rental_object->>'rent')::int)
            ) AS weighted_score
        FROM
            properties p,
            jsonb_array_elements(p.data->'schools'->'colleges') AS c(college)
        CROSS JOIN LATERAL
            jsonb_array_elements(p.data->'rentals') AS rental_object
        WHERE
            c.college @> '{{"name": "{prefs.get("campus", "Texas A&M University")}"}}'
            AND (rental_object->>'rent')::int <= {prefs.get("max_rent", 10000)}
            AND (rental_object->>'squareFeet')::int >= {prefs.get("min_sqft", 0)}
        ORDER BY weighted_score DESC
        LIMIT 50
        OFFSET (1 - 1) * 50;
    ''')
    
    with engine.connect() as connection:
        result = connection.execute(query).fetchall()

    data = {} 

    for row in result:
        data["property_id"] = row[0]
        data["property_data"] = row[1]
        data["rental_object"] = row[2]
        data["score"] = row[3]

    return data

def get_prefs_query(id):
    id = int(id)
    result = supabase.table("User").select("preferences").eq("id", id).execute()

    preferences = result.data[0]['preferences']

    return preferences

get_recs_query(get_prefs_query(5))

# Execute the raw SQL query
@app.route('/get_recommendations', methods=['GET'])
def get_recs_api():
    id = request.headers.get('id')

    if not id:
        return jsonify({'error': 'Missing id header'}), 400
    
    try:
        prefs = get_prefs_query(id)
        recs = get_recs_query(prefs)

        return jsonify(recs)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500