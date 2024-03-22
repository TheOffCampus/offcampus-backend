from flask import Flask, request, jsonify
from supabase import create_client, Client
from sqlalchemy import create_engine, text
from flask_cors import CORS


app = Flask(__name__)
CORS(app, resources={r'/*': {'origins': '*'}})

SUPABASE_URL='https://ihnradjuxnddmmioyeqp.supabase.co/'
SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlobnJhZGp1eG5kZG1taW95ZXFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDc5NDkyODcsImV4cCI6MjAyMzUyNTI4N30.cebjm2GbItaRLa81OYTi3Suffy8u52hO3lSRgjrK5r8'
SQLALCHEMY_DATABASE_URL = "postgresql://postgres.ihnradjuxnddmmioyeqp:oMbKlcQqT9APDtKG@aws-0-us-west-1.pooler.supabase.com/postgres"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def get_recs_query(prefs):
    """
	Generate and execute a raw SQL query to find property recommendations based on user preferences.

	Args:
    	prefs (dict): User preferences including weights for miles, square footage, and rent,
                  	as well as filters for campus name, maximum rent, and minimum square footage.

	Returns:
    	list of dicts: List of recommended properties with details and calculated scores.
	"""
    query = text(f'''
        SELECT
            p.id AS property_id,
            p.data AS property_data,
            rental_object,
            (
                ({prefs.get("miles_weight", 0.5)} * -1 * 1000 * (c.college->>'miles')::float) +
                ({prefs.get("sqft_weight", 0.5)} * 1 * 800 * (rental_object->>'squareFeet')::int) +
                ({prefs.get("rent_weight", 0.5)} * -1 * (rental_object->>'rent')::int)
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
        LIMIT 5
        OFFSET (1 - 1) * 50;
    ''')
    
    with engine.connect() as connection:
        result = connection.execute(query).fetchall()

    print("results: ", result[0][1])
    data = []
    for row in result:
        row_data = {
            "property_id": row[0],
            "property_data": row[1],
            "rental_object": row[2],
            "score": row[3]
        }
        data.append(row_data)

    return data

def get_prefs_query(id):
    """
	Retrieve user preferences from the Supabase 'User' table by user ID.

	Args:
    	id (int): User ID.

	Returns:
    	dict: User preferences stored in the database.
	"""
    result = supabase.table("User").select("preferences").eq("id", id).execute()

    preferences = result.data[0]['preferences']

    return preferences

get_recs_query(get_prefs_query(5))

# Execute the raw SQL query
@app.route('/get_recommendations', methods=['GET'])
def get_recs_api():
    """
	API endpoint to get property recommendations for a user based on their stored preferences.

	Expects an 'id' header with the user's ID.
	Returns a JSON response with simplified property recommendation details or an error message.
	"""
    id = request.headers.get('id')

    if not id:
        return jsonify({'error': 'Missing id header'}), 400

    try:
        prefs = get_prefs_query(id)
        recs = get_recs_query(prefs)

        simplified_recs = []
        for rec in recs:
            price = rec['property_data']['models'][0].get('rentLabel', 'N/A')
            price_cleaned = price.replace('/ Person', '').strip()
            simplified_rec = {
                'id': rec['property_id'],
                'name': rec['property_data'].get('propertyName', 'N/A'),
                'modelName': rec['rental_object'].get('modelName'),
                'rent': rec['rental_object'].get('rent'),
                'modelImage': rec['rental_object'].get('image'),
                'address': rec['property_data']['location'].get('fullAddress', 'N/A'),
                'price': price_cleaned,
                'score': rec['score'],
                'photos': rec['property_data'].get('photos', [''])
            }
            simplified_recs.append(simplified_rec)

        return jsonify(simplified_recs)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500