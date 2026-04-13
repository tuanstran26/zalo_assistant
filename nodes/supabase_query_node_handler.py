from supabase import create_client
import os


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_excel_file_names():
    res = supabase.table("excel_files").select("file_name").execute()
    return [r["file_name"] for r in res.data]


def run(step, context):
    result = get_excel_file_names()
    context.set("excel_file_list", result)
    return {"excel_file_list": result}, step.get("next")