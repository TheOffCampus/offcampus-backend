from flask import Flask, request, jsonify
from supabase import create_client, Client
from sqlalchemy import create_engine


app = Flask(__name__)

SUPABASE_URL='https://ihnradjuxnddmmioyeqp.supabase.co/'
SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlobnJhZGp1eG5kZG1taW95ZXFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDc5NDkyODcsImV4cCI6MjAyMzUyNTI4N30.cebjm2GbItaRLa81OYTi3Suffy8u52hO3lSRgjrK5r8'
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:oMbKlcQqT9APDtKG@aws-0-us-west-1.pooler.supabase.com:5432/postgres"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def get_recs_query(prefs):
    prefs = {
        'rent_weight': prefs['rent_weight'],
        'sqft_weight': prefs['sqft_weight'],
        'miles_weight': prefs['miles_weight'],
    }

    result = supabase.rpc("get_recs", prefs).execute()

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
        prefs = get_prefs_query(id)
        recs = get_recs_query(prefs)

        return recs
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

