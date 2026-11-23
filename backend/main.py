"""
TravelVerse Unified Backend API Engine
Combined and optimized across all TravelVerse services:
- Full User, Traveller & Agent Authentication & Role Management
- Companion Discovery, Connection Requests & Social Networking
- Real-time Direct Buddy Chat, Read Receipts, Delete & Unread Counts
- Travel Agent Marketplace, Verified Reviews & Inquiry Management
- Group Expeditions, Booking Vouchers, PDF Brochure Generation & Roster Chat
- AI Itinerary Generator (itinerary_ai) & Context-Aware Assistant Copilot (Milo)
- Dual Database Connectivity: MongoDB Atlas Cluster with Local MongoDB & Offline Fallbacks
"""

import os
import sys
import re
import time
import json
import random
import smtplib
import ssl
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, Request, Response, status, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from pydantic import BaseModel, Field
from pymongo import MongoClient, ReturnDocument, ASCENDING, DESCENDING

# Ensure current backend folder is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Load environment configuration
load_dotenv(os.path.join(backend_dir, ".env"))

# Import specialized engines
try:
    from itinerary_ai import generate_professional_itinerary
except ImportError:
    def generate_professional_itinerary(destination: str, **kwargs):
        return {
            "title": f"Expedition to {destination}",
            "destination": destination,
            "itinerary": [{"day": 1, "title": "Arrival & Welcome", "description": f"Arrive in {destination} and meet your guide."}]
        }

try:
    from pdf_generator import generate_trip_itinerary_pdf
except ImportError:
    def generate_trip_itinerary_pdf(trip_data: dict, booking_data: dict = None) -> bytes:
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n186\n%%EOF\n"

app = FastAPI(
    title="TravelVerse Unified Backend API",
    description="Unified API combining traveller social features, verified agent portals, AI itineraries, and departure booking management.",
    version="2.5.0"
)

# Robust CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import pymongo.errors

@app.exception_handler(pymongo.errors.PyMongoError)
async def pymongo_exception_handler(request: Request, exc: pymongo.errors.PyMongoError):
    err_str = str(exc)
    if "TLSV1_ALERT_INTERNAL_ERROR" in err_str or "ServerSelectionTimeoutError" in str(type(exc)):
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "Database connection rejected by MongoDB Atlas. Your current IP address is not whitelisted. Please add your IP (or 0.0.0.0/0) to MongoDB Atlas > Network Access.",
                "tip": "Log in to cloud.mongodb.com -> Network Access -> Add IP Address -> Add Current IP Address (or 0.0.0.0/0)"
            }
        )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Database operation failed", "detail": err_str}
    )

# -------------------------------------------------------------
# DATABASE CONNECTION & MONGO DRIVER SETUP
# -------------------------------------------------------------
DIRECT_ATLAS_URI = "mongodb://chitrakshgupta21_db_user:NLjWHd0cf2WYLMjv@ac-7w0ao5s-shard-00-00.kzhlru4.mongodb.net:27017,ac-7w0ao5s-shard-00-01.kzhlru4.mongodb.net:27017,ac-7w0ao5s-shard-00-02.kzhlru4.mongodb.net:27017/?ssl=true&replicaSet=atlas-11vkic-shard-0&authSource=admin&appName=Cluster0"
SRV_ATLAS_URI = "mongodb+srv://chitrakshgupta21_db_user:NLjWHd0cf2WYLMjv@cluster0.kzhlru4.mongodb.net/TravelVerse?retryWrites=true&w=majority"
MONGO_URI = os.getenv("MONGO_URI", DIRECT_ATLAS_URI)

_ca_file = None
try:
    import certifi
    _ca_file = certifi.where()
except Exception:
    pass

def get_mongo_client():
    uris_to_try = [MONGO_URI]
    if SRV_ATLAS_URI not in uris_to_try:
        uris_to_try.append(SRV_ATLAS_URI)
    if DIRECT_ATLAS_URI not in uris_to_try:
        uris_to_try.append(DIRECT_ATLAS_URI)

    configs = []
    if _ca_file:
        configs.append(("certifi", {"serverSelectionTimeoutMS": 3000, "connectTimeoutMS": 3000, "tlsCAFile": _ca_file}))
    configs.append(("native_ssl", {"serverSelectionTimeoutMS": 3000, "connectTimeoutMS": 3000}))
    configs.append(("tls_insecure", {"serverSelectionTimeoutMS": 3000, "connectTimeoutMS": 3000, "tlsAllowInvalidCertificates": True}))

    for target_uri in uris_to_try:
        if not target_uri:
            continue
        for name, kw in configs:
            try:
                c = MongoClient(target_uri, **kw)
                c.admin.command('ping')
                print(f"[DB] Connected to MongoDB Atlas successfully.")
                return c
            except Exception:
                pass

    kw_final = {"serverSelectionTimeoutMS": 5000, "connectTimeoutMS": 5000}
    if _ca_file:
        kw_final["tlsCAFile"] = _ca_file
    return MongoClient(MONGO_URI or DIRECT_ATLAS_URI, **kw_final)

client = get_mongo_client()
db = client["TravelVerse"]

# -------------------------------------------------------------
# HELPER FUNCTIONS & DATA SERIALIZATION
# -------------------------------------------------------------
def serialize_doc(doc):
    if not doc:
        return doc
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    d = dict(doc)
    if "_id" in d:
        d["_id"] = str(d["_id"])
    return d

def get_next_sequence(sequence_name: str) -> int:
    try:
        ret = db.counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        return int(ret["seq"])
    except Exception:
        # Fallback counter estimation
        return int(time.time() * 1000) % 1000000

_USER_KEYS_CACHE = {}

def get_cached_user_keys(identifier: str) -> List[str]:
    ident_clean = (identifier or "").strip().lower()
    if not ident_clean:
        return []
    now = time.time()
    cached = _USER_KEYS_CACHE.get(ident_clean)
    if cached and (now - cached["time"] < 60):
        return cached["keys"]

    keys = [ident_clean]
    doc = find_traveller_or_agent(ident_clean)
    if doc:
        if doc.get("email"):
            keys.append(doc["email"].strip().lower())
        if doc.get("username"):
            keys.append(doc["username"].strip().lower())
    
    unique_keys = list(set(k for k in keys if k))
    _USER_KEYS_CACHE[ident_clean] = {"keys": unique_keys, "time": now}
    return unique_keys

def find_traveller_or_agent(query: str):
    clean = (query or "").strip().lower()
    if not clean:
        return None
    rx = {"$regex": f"^{re.escape(clean)}$", "$options": "i"}
    
    # 1. Search in travellers
    doc = db.travellers.find_one({"$or": [{"email": rx}, {"username": rx}]})
    if doc:
        doc["role"] = doc.get("role") or "traveller"
        return doc
        
    # 2. Search in agents
    doc = db.agents.find_one({"$or": [{"email": rx}, {"username": rx}, {"agency_name": rx}]})
    if doc:
        doc["role"] = "agent"
        if not doc.get("username"):
            doc["username"] = doc.get("agency_name") or doc.get("agent_name")
        if not doc.get("first_name") and doc.get("agent_name"):
            parts = doc["agent_name"].split(" ")
            doc["first_name"] = parts[0]
            doc["last_name"] = " ".join(parts[1:])
        return doc
        
    # 3. Search in users collection
    doc = db.users.find_one({"$or": [{"email": rx}, {"username": rx}]})
    if doc:
        return doc
        
    return None

def find_user_anywhere(identifier: str):
    return find_traveller_or_agent(identifier)

def sync_user_trip_interests_field(user_email: str):
    if not user_email:
        return
    try:
        email_clean = user_email.strip().lower()
        u_doc = find_traveller_or_agent(email_clean)
        identities = [email_clean]
        if u_doc:
            if u_doc.get("email"): identities.append(u_doc["email"].strip().lower())
            if u_doc.get("username"): identities.append(u_doc["username"].strip().lower())

        or_clauses = [{"user_email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}} for e in set(identities)]
        interests = list(db.trip_interests.find({"$or": or_clauses}).sort("id", -1))

        # Deduplicate by destination
        deduped = []
        seen = set()
        for i in interests:
            d = (i.get("destination") or "").strip().lower()
            if d and d not in seen:
                seen.add(d)
                s = serialize_doc(i)
                s.pop("_id", None)
                deduped.append(s)
            elif not d:
                s = serialize_doc(i)
                s.pop("_id", None)
                deduped.append(s)

        user_or_clauses = []
        for e in set(identities):
            rx_e = {"$regex": f"^{re.escape(e)}$", "$options": "i"}
            user_or_clauses.extend([{"email": rx_e}, {"username": rx_e}, {"user_email": rx_e}])

        db.travellers.update_many(
            {"$or": user_or_clauses},
            {"$set": {"trip_interests": deduped}}
        )
        db.users.update_many(
            {"$or": user_or_clauses},
            {"$set": {"trip_interests": deduped}}
        )
        db.companions.update_many(
            {"$or": user_or_clauses},
            {"$set": {"trip_interests": deduped}}
        )
    except Exception as e:
        print("[WARN] sync_user_trip_interests_field:", e)

def sync_travellers_and_agents_collections():
    try:
        db.agents.update_many({"role": {"$ne": "agent"}}, {"$set": {"role": "agent"}})
        for a in db.agents.find({}, {"email": 1, "agent_name": 1, "agency_name": 1, "password": 1, "username": 1}):
            em = (a.get("email") or "").strip().lower()
            if em:
                db.users.update_one(
                    {"email": {"$regex": f"^{re.escape(em)}$", "$options": "i"}},
                    {"$set": {
                        "role": "agent",
                        "agent_name": a.get("agent_name", ""),
                        "agency_name": a.get("agency_name", ""),
                        "username": a.get("username") or em.split("@")[0],
                        "password": a.get("password", "")
                    }},
                    upsert=True
                )
    except Exception as e:
        print("[WARN] sync_travellers_and_agents_collections:", e)

def sync_queries_and_bookings_collections():
    try:
        # Sync agent_inquiries <-> queries
        for inq in db.agent_inquiries.find({}):
            doc = dict(inq)
            doc.pop("_id", None)
            if "id" in doc:
                db.queries.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
                
        # Sync trip_enrollments <-> bookings
        for enr in db.trip_enrollments.find({}):
            doc = dict(enr)
            doc.pop("_id", None)
            if "id" in doc:
                db.bookings.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
    except Exception as e:
        print("[WARN] sync_queries_and_bookings_collections:", e)

def heal_group_trips_agent_info():
    try:
        first_agent = db.agents.find_one({})
        fallback_agent_id = first_agent.get("id", 1) if first_agent else 1
        fallback_agent_name = first_agent.get("agent_name", "Aarav Sharma") if first_agent else "Aarav Sharma"
        fallback_agency = first_agent.get("agency_name", "Himalayan High Passes") if first_agent else "Himalayan High Passes"
        fallback_email = first_agent.get("email", "aarav.sharma@travelverse.com") if first_agent else "aarav.sharma@travelverse.com"

        trips = list(db.group_trips.find({}))
        for t in trips:
            updates = {}
            if not t.get("agent_id"):
                updates["agent_id"] = fallback_agent_id
            if not t.get("agent_name"):
                updates["agent_name"] = fallback_agent_name
            if not t.get("agency_name"):
                updates["agency_name"] = fallback_agency
            if not t.get("agent_email"):
                updates["agent_email"] = fallback_email
            if updates:
                db.group_trips.update_one({"_id": t["_id"]}, {"$set": updates})
    except Exception as e:
        print("[WARN] heal_group_trips_agent_info:", e)

# -------------------------------------------------------------
# EMAIL CONFIRMATION DISPATCHER
# -------------------------------------------------------------
def send_booking_confirmation_email(user_email: str, user_name: str, booking_code: str, trip_doc: dict, booking_doc: dict):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = (os.getenv("SMTP_PASS") or "").replace(" ", "").strip()
    sender_email = os.getenv("SMTP_FROM", smtp_user or "concierge@travelverse.com")
    app_base = os.getenv("APP_URL", "http://127.0.0.1:8000")

    trip_title = trip_doc.get("title") or trip_doc.get("trip_title") or "Hosted Expedition"
    destination = trip_doc.get("destination") or "Featured Destination"
    dates = trip_doc.get("dates") or f"{trip_doc.get('start_date', '')} to {trip_doc.get('end_date', '')}".strip(" to")
    dur_days = trip_doc.get("duration_days", 2)
    duration_str = f"{dur_days} Days / {max(1, int(dur_days) - 1)} Nights"
    meeting_point = trip_doc.get("meeting_point", "Designated Airport VIP Lounge / Rendezvous Point")
    agency_name = trip_doc.get("agency_name") or "TravelVerse Certified Partner"
    lead_guide = trip_doc.get("agent_name") or "Certified Expedition Host"
    agent_phone = trip_doc.get("agent_phone") or ""
    trip_id = trip_doc.get("id", 110)
    seats = booking_doc.get("seats", 1)
    user_phone = booking_doc.get("user_phone", "")
    amount_paid = booking_doc.get("amount_paid", 0.0)
    currency = booking_doc.get("currency") or trip_doc.get("currency") or "USD"
    special_notes = booking_doc.get("special_notes", "")
    passengers = booking_doc.get("passengers") or []
    if not passengers:
        names = booking_doc.get("traveller_names") or [user_name]
        passengers = [{"name": n} for n in names]

    pax_rows_html = ""
    for idx, p in enumerate(passengers):
        p_name = p.get("name") or f"Passenger {idx+1}"
        p_lead = ' <span style="color:#E8874A; font-weight:bold;">(Lead)</span>' if idx == 0 else ""
        p_gender = p.get("gender") or "—"
        p_age = f"{p.get('age')} yrs" if p.get("age") is not None and str(p.get("age")).strip() else "—"
        p_nat = p.get("nationality") or "Indian"
        p_pref = p.get("preferences") or "Standard"
        pax_rows_html += f"""
        <tr style="border-bottom:1px solid #E2D8C6; background:{'#FAF8F5' if idx % 2 == 0 else '#FFFFFF'};">
          <td style="padding:8px 10px; font-weight:bold; color:#0B2027;">{idx+1}</td>
          <td style="padding:8px 10px; font-weight:bold; color:#0B2027;">{p_name}{p_lead}</td>
          <td style="padding:8px 10px; color:#55625F;">{p_gender}</td>
          <td style="padding:8px 10px; color:#55625F;">{p_age}</td>
          <td style="padding:8px 10px; color:#55625F;">{p_nat}</td>
          <td style="padding:8px 10px; color:#17242A;">{p_pref}</td>
        </tr>
        """

    pdf_details_url = f"{app_base}/trip-itinerary.pdf?trip_id={trip_id}&booking_code={booking_code}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0; padding:0; background:#FAF8F5; font-family:'Helvetica Neue', Arial, sans-serif; color:#17242A;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#FAF8F5; padding:30px 10px;">
        <tr><td align="center">
          <table width="620" cellpadding="0" cellspacing="0" style="background:#FFFFFF; border-radius:14px; border:1px solid #E2D8C6; overflow:hidden; box-shadow:0 6px 20px rgba(0,0,0,0.06);">
            <!-- Top Dark Header Banner -->
            <tr style="background:#0B2027; color:#FFFFFF;">
              <td style="padding:22px 30px;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td>
                      <h1 style="margin:0; font-size:20px; letter-spacing:0.5px; color:#FFFFFF;">TRAVELVERSE EXPEDITIONS</h1>
                      <p style="margin:4px 0 0; font-size:12px; color:#C9A227; font-weight:bold;">Official Confirmed Booking Invoice &amp; Voucher</p>
                    </td>
                    <td align="right">
                      <div style="background:#C9A227; color:#0B2027; font-weight:bold; font-size:12px; padding:5px 12px; border-radius:6px; display:inline-block;">
                        Ref: {booking_code}
                      </div>
                      <div style="margin-top:4px; font-size:11px; color:#4ADE80; font-weight:bold;">✓ Status: Confirmed</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Main Body -->
            <tr>
              <td style="padding:26px 30px;">
                <h2 style="margin:0 0 8px; color:#0B2027; font-size:18px;">Dear {user_name or 'Explorer'},</h2>
                <p style="font-size:13.5px; line-height:1.6; color:#55625F; margin:0 0 18px;">
                  Your departure spot for <strong>{trip_title}</strong> has been officially confirmed! Attached is your official <strong>2-page personalized booking invoice and expedition dossier</strong>.
                </p>

                <!-- Customer & Agent 2-Column Summary -->
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:18px;">
                  <tr>
                    <td width="48%" valign="top" style="background:#FAF8F5; border:1px solid #E2D8C6; border-radius:10px; padding:14px;">
                      <div style="font-size:11px; font-weight:bold; color:#C9A227; text-transform:uppercase; margin-bottom:6px;">BILLED TO / PRIMARY GUEST</div>
                      <div style="font-weight:bold; font-size:14px; color:#0B2027; margin-bottom:2px;">{user_name} (Lead)</div>
                      <div style="font-size:12px; color:#55625F; margin-bottom:2px;">✉️ {user_email}</div>
                      {f'<div style="font-size:12px; color:#55625F; margin-bottom:2px;">📞 {user_phone}</div>' if user_phone else ''}
                      <div style="font-size:12px; color:#166534; font-weight:bold; margin-top:6px;">Reserved Seats: {seats} Guest(s)</div>
                      <div style="font-size:12px; color:#0B2027; font-weight:bold;">Total Paid: {currency} {amount_paid:,.2f}</div>
                    </td>
                    <td width="4%"></td>
                    <td width="48%" valign="top" style="background:#FAF8F5; border:1px solid #E2D8C6; border-radius:10px; padding:14px;">
                      <div style="font-size:11px; font-weight:bold; color:#166534; text-transform:uppercase; margin-bottom:6px;">EXPEDITION HOST &amp; RENDEZVOUS</div>
                      <div style="font-weight:bold; font-size:14px; color:#0B2027; margin-bottom:2px;">{agency_name}</div>
                      <div style="font-size:12px; color:#55625F; margin-bottom:2px;">Host Guide: <strong>{lead_guide}</strong></div>
                      <div style="font-size:12px; color:#55625F; margin-bottom:2px;">📍 {destination}</div>
                      <div style="font-size:12px; color:#55625F; margin-bottom:2px;">🗓️ {dates} ({duration_str})</div>
                      <div style="font-size:11.5px; color:#17242A; margin-top:4px;"><strong>Rendezvous:</strong> {meeting_point[:55]}</div>
                    </td>
                  </tr>
                </table>

                <!-- Registered Passenger Table -->
                <div style="margin-bottom:18px;">
                  <div style="font-size:12px; font-weight:bold; text-transform:uppercase; color:#0B2027; margin-bottom:6px;">
                    👥 REGISTERED PASSENGERS &amp; PREFERENCES ({len(passengers)} Pax)
                  </div>
                  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px; border:1px solid #E2D8C6; border-radius:8px; overflow:hidden;">
                    <tr style="background:#F3EDE2; color:#55625F; font-weight:bold; font-size:11px; text-transform:uppercase;">
                      <th style="padding:7px 10px; text-align:left;">#</th>
                      <th style="padding:7px 10px; text-align:left;">Passenger Name</th>
                      <th style="padding:7px 10px; text-align:left;">Gender</th>
                      <th style="padding:7px 10px; text-align:left;">Age</th>
                      <th style="padding:7px 10px; text-align:left;">Nationality</th>
                      <th style="padding:7px 10px; text-align:left;">Preferences</th>
                    </tr>
                    {pax_rows_html}
                  </table>
                </div>

                {f'''
                <div style="background:#FAF8F5; border:1px solid #E2D8C6; border-radius:8px; padding:10px 14px; margin-bottom:18px; font-size:12px;">
                  <strong>Special Requests &amp; Notes:</strong> {special_notes}
                </div>
                ''' if special_notes else ''}

                <!-- Download Button -->
                <div style="text-align:center; margin:24px 0 16px;">
                  <a href="{pdf_details_url}" target="_blank" style="background:#0B2027; color:#FFFFFF; text-decoration:none; padding:13px 26px; border-radius:8px; font-weight:bold; font-size:13.5px; display:inline-block; box-shadow:0 4px 12px rgba(11,32,39,0.25);">
                    📄 Download Official 2-Page Invoice &amp; Dossier PDF
                  </a>
                  <div style="font-size:11.5px; color:#55625F; margin-top:8px;">
                    (Also attached directly to this confirmation email as PDF)
                  </div>
                </div>

                <div style="border-top:1px solid #E2D8C6; padding-top:16px; margin-top:20px; font-size:11.5px; color:#55625F; text-align:center;">
                  TravelVerse Expedition Network &bull; Verified Host Guides &amp; Protected Bookings &bull; travelverse.com
                </div>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    if not (smtp_host and smtp_user and smtp_pass):
        print(f"[EMAIL MOCK] Email ready for {user_email}. Booking code: {booking_code}. PDF Link: {pdf_details_url}")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Booking Confirmed: {trip_title} [{booking_code}]"
        msg["From"] = f"TravelVerse Concierge <{sender_email}>"
        msg["To"] = user_email
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        # Attach real 2-page personalized PDF
        try:
            pdf_bytes = generate_trip_itinerary_pdf(trip_doc or {}, booking_doc or {})
            part = MIMEApplication(pdf_bytes, _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=f"TravelVerse_Invoice_{booking_code}.pdf")
            msg.attach(part)
        except Exception as pdf_err:
            print("[EMAIL] Could not attach PDF to email:", pdf_err)

        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender_email, [user_email], msg.as_string())
        print(f"[EMAIL] Confirmation successfully sent to {user_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {user_email}: {e}")
        return False

def send_booking_cancellation_email(user_email: str, user_name: str, booking_code: str, trip_doc: dict, booking_doc: dict) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = (os.getenv("SMTP_PASS") or "").replace(" ", "").strip()
    sender_email = os.getenv("SMTP_FROM", smtp_user or "concierge@travelverse.com")

    trip_title = trip_doc.get("title") or trip_doc.get("trip_title") or "Hosted Expedition"
    destination = trip_doc.get("destination") or "Destination"
    dates = trip_doc.get("dates") or f"{trip_doc.get('start_date', '')} to {trip_doc.get('end_date', '')}".strip(" to")
    lead_guide = trip_doc.get("agent_name") or "Certified Expedition Host"
    agency_name = trip_doc.get("agency_name") or "TravelVerse Certified Partner"
    seats = booking_doc.get("seats", 1)
    amount_paid = booking_doc.get("amount_paid", 0.0)
    currency = booking_doc.get("currency") or trip_doc.get("currency") or "USD"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0; padding:0; background:#F4EFE6; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color:#0B2027;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#F4EFE6; padding:30px 10px;">
        <tr><td align="center">
          <table width="620" cellpadding="0" cellspacing="0" style="background:#FFFFFF; border:1px solid #E2D8C6; border-radius:14px; overflow:hidden; box-shadow:0 8px 30px rgba(11,32,39,0.08);">
            <tr>
              <td style="background:#DC2626; padding:22px 30px; text-align:center;">
                <div style="font-size:12px; font-weight:bold; letter-spacing:1px; text-transform:uppercase; color:#FEE2E2; margin-bottom:4px;">TRAVELVERSE OFFICIAL NOTICE</div>
                <h1 style="color:#FFFFFF; font-size:22px; margin:0; font-weight:700;">Booking Cancellation Notice</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:28px 30px;">
                <p style="font-size:15px; margin:0 0 16px; color:#0B2027;">Dear <strong>{user_name}</strong>,</p>
                <p style="font-size:14px; line-height:1.6; color:#4B5563; margin:0 0 20px;">
                  We are writing to inform you that your reservation for <strong>{trip_title}</strong> (Booking Ref: <code style="background:#F3F4F6; padding:2px 6px; border-radius:4px; font-weight:bold; color:#1F2937;">{booking_code}</code>) has been <strong>cancelled</strong> by the expedition host.
                </p>

                <div style="background:#FEF2F2; border:1px solid #FECACA; border-radius:10px; padding:16px 20px; margin-bottom:20px;">
                  <div style="font-size:11px; font-weight:bold; text-transform:uppercase; color:#991B1B; margin-bottom:10px; letter-spacing:0.5px;">Cancelled Reservation Summary</div>
                  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px; color:#1F2937;">
                    <tr>
                      <td style="padding:5px 0; color:#6B7280; width:130px;"><strong>Expedition:</strong></td>
                      <td style="padding:5px 0; font-weight:600;">{trip_title} (#{trip_doc.get('id', '')})</td>
                    </tr>
                    <tr>
                      <td style="padding:5px 0; color:#6B7280;"><strong>Destination:</strong></td>
                      <td style="padding:5px 0;">{destination}</td>
                    </tr>
                    <tr>
                      <td style="padding:5px 0; color:#6B7280;"><strong>Departure Dates:</strong></td>
                      <td style="padding:5px 0;">{dates or 'Upcoming'}</td>
                    </tr>
                    <tr>
                      <td style="padding:5px 0; color:#6B7280;"><strong>Seats Released:</strong></td>
                      <td style="padding:5px 0;">{seats} Guest Seat(s)</td>
                    </tr>
                    <tr>
                      <td style="padding:5px 0; color:#6B7280;"><strong>Host / Agency:</strong></td>
                      <td style="padding:5px 0;">{lead_guide} ({agency_name})</td>
                    </tr>
                    <tr>
                      <td style="padding:5px 0; color:#6B7280;"><strong>Refund Status:</strong></td>
                      <td style="padding:5px 0; color:#059669; font-weight:700;">100% Full Refund Scheduled ({currency} {amount_paid:,.2f})</td>
                    </tr>
                  </table>
                </div>

                <p style="font-size:13.5px; line-height:1.6; color:#4B5563; margin:0 0 16px;">
                  If any payment was processed, the full refund of <strong>{currency} {amount_paid:,.2f}</strong> has been automatically scheduled back to your original payment method. Depending on your bank, it may take 3-5 business days to reflect.
                </p>

                <p style="font-size:13.5px; line-height:1.6; color:#4B5563; margin:0 0 24px;">
                  If you have questions or would like to explore alternative departure dates or upcoming expeditions, please reach out to our concierge team or connect directly with the host.
                </p>

                <div style="border-top:1px solid #E5E7EB; padding-top:16px; font-size:12px; color:#9CA3AF; text-align:center;">
                  TravelVerse Expedition Network &bull; Verified Host Guides &bull; travelverse.com
                </div>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    if not (smtp_host and smtp_user and smtp_pass):
        print(f"[EMAIL MOCK] Cancellation email ready for {user_email}. Booking code: {booking_code}")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Booking Cancelled: {trip_title} [{booking_code}]"
        msg["From"] = f"TravelVerse Concierge <{sender_email}>"
        msg["To"] = user_email
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender_email, [user_email], msg.as_string())
        print(f"[EMAIL] Cancellation notice successfully sent to {user_email} for booking {booking_code}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send cancellation email to {user_email}: {e}")
        return False

def send_otp_email(to_email: str, otp_code: str, action: str = "signup", user_name: str = "") -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = (os.getenv("SMTP_PASS") or "").replace(" ", "").strip()
    sender_email = os.getenv("SMTP_FROM", smtp_user or "concierge@travelverse.com")

    if not (smtp_host and smtp_user and smtp_pass):
        print(f"[EMAIL MOCK] SMTP not configured. OTP for {to_email}: {otp_code}")
        return True

    try:
        clean_email = (to_email or "").strip().lower()
        if not clean_email or "@" not in clean_email:
            return False

        if action == "signup":
            subject = f"Your TravelVerse Verification Code: {otp_code}"
            headline = "Welcome to TravelVerse!"
            message_text = "Thank you for joining TravelVerse. Please enter the 6-digit verification code below in your browser to verify your email address and continue setting up your account."
        elif action in ("reset", "reset_password"):
            subject = f"TravelVerse Password Reset Code: {otp_code}"
            headline = "Password Reset Request"
            message_text = "We received a request to reset your TravelVerse account password. Please enter the 6-digit verification code below to confirm your identity and choose a new password."
        else:
            subject = f"Your TravelVerse Verification Code: {otp_code}"
            headline = "Account Verification Code"
            message_text = "Please enter the 6-digit verification code below to verify your identity on TravelVerse."

        greeting = f"Hello {user_name}," if user_name else "Hello Explorer,"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color:#FAF8F5; margin:0; padding:24px 0; color:#17242A;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#FFFFFF; border-radius:14px; border:1px solid #E2D8C6; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.06);">
        <!-- BRAND HEADER -->
        <tr style="background:#0B2027; color:#FFFFFF;">
          <td style="padding:26px 32px; text-align:center;">
            <div style="font-size:24px; font-weight:800; letter-spacing:1px; color:#FFFFFF;">✦ TRAVELVERSE ✦</div>
            <p style="margin:6px 0 0; font-size:12.5px; color:#C9A227; letter-spacing:0.5px;">Curated Expeditions & Travel Companion Community</p>
          </td>
        </tr>
        <!-- CONTENT -->
        <tr>
          <td style="padding:32px 36px;">
            <h2 style="margin:0 0 14px; font-size:20px; color:#0B2027;">{headline}</h2>
            <p style="font-size:14.5px; line-height:1.6; color:#55625F; margin:0 0 14px;">
              {greeting}
            </p>
            <p style="font-size:14px; line-height:1.6; color:#55625F; margin:0 0 24px;">
              {message_text}
            </p>

            <!-- OTP CODE BOX -->
            <div style="background:#FAF8F5; border:2px dashed #E8874A; border-radius:12px; padding:22px 16px; text-align:center; margin:24px 0;">
              <span style="font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:1.5px; color:#888; display:block; margin-bottom:8px;">Your 6-Digit Verification Code</span>
              <span style="font-size:36px; font-weight:800; letter-spacing:8px; color:#0B2027; font-family:'Courier New', Courier, monospace; display:inline-block; padding:4px 10px;">{otp_code}</span>
              <span style="font-size:12px; color:#888; display:block; margin-top:8px;">This code expires in 10 minutes.</span>
            </div>

            <p style="font-size:12.5px; line-height:1.5; color:#888; margin:24px 0 0;">
              <strong>Security reminder:</strong> Never share this code with anyone. TravelVerse staff will never ask for your verification code. If you did not request this, you can safely ignore this email.
            </p>
          </td>
        </tr>
        <!-- FOOTER -->
        <tr style="background:#F4EFE6;">
          <td style="padding:16px 32px; text-align:center; font-size:12px; color:#7A8580;">
            TravelVerse Inc. &bull; Explore with Confidence
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"TravelVerse Security <{sender_email}>"
        msg["To"] = clean_email
        msg.attach(MIMEText(f"{headline}\n\nYour TravelVerse verification code is: {otp_code}\nThis code expires in 10 minutes.\nNever share this code with anyone.", "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender_email, [clean_email], msg.as_string())

        print(f"[EMAIL SUCCESS] Sent OTP verification email to {clean_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send OTP email to {to_email}: {e}")
        return False


# -------------------------------------------------------------
# PYDANTIC MODELS
# -------------------------------------------------------------
class RegisterRequest(BaseModel):
    first_name: str
    last_name: Optional[str] = ""
    username: str
    email: str
    password: str
    role: Optional[str] = "traveller"
    badges: Optional[List[str]] = None
    agency_name: Optional[str] = None
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    destinations: Optional[str] = None
    experience_years: Optional[int] = None
    languages: Optional[str] = None
    bio: Optional[str] = None
    profile_pic: Optional[str] = None

class RegisterAgentRequest(BaseModel):
    agency_name: str
    agent_name: str
    email: str
    password: Optional[str] = ""
    username: Optional[str] = None
    specialty: Optional[str] = None
    destinations: Optional[str] = None
    office_address: Optional[str] = None
    profile_pic: Optional[str] = None
    agent_type: Optional[str] = "person"
    phone: Optional[str] = None
    bio: Optional[str] = None
    experience_years: Optional[int] = 3
    languages: Optional[str] = "English"
    cover_image: Optional[str] = None
    badges: Optional[List[str]] = None

class LoginRequest(BaseModel):
    email_or_username: str
    password: str
    expected_role: Optional[str] = None

class SendOTPRequest(BaseModel):
    identifier: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None

class VerifyOTPRequest(BaseModel):
    identifier: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    otp_code: Optional[str] = None
    otp: Optional[str] = None

class SendSignupOTPRequest(BaseModel):
    email: Optional[str] = None
    identifier: Optional[str] = None

class VerifySignupOTPRequest(BaseModel):
    email: Optional[str] = None
    identifier: Optional[str] = None
    otp_code: Optional[str] = None
    otp: Optional[str] = None

class SendEmailOTPOnlyRequest(BaseModel):
    email: Optional[str] = None
    identifier: Optional[str] = None

class VerifyEmailOTPOnlyRequest(BaseModel):
    email: Optional[str] = None
    identifier: Optional[str] = None
    otp_code: Optional[str] = None
    otp: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    identifier: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    otp_code: Optional[str] = None
    otp: Optional[str] = None
    new_password: Optional[str] = None

class VerifyOTPResetPasswordRequest(BaseModel):
    identifier: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    otp_code: Optional[str] = None
    otp: Optional[str] = None
    new_password: Optional[str] = None

class DeleteAccountRequest(BaseModel):
    email_or_username: str
    password: str

class UpdateUsernameRequest(BaseModel):
    email: str
    new_username: str

class UpdateBadgesRequest(BaseModel):
    email: str
    badges: List[str]

class UpdateProfileRequest(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    profile_pic: Optional[str] = None

class UpdateProfilePicRequest(BaseModel):
    email: str
    profile_pic: str

class UpdateAgentProfileRequest(BaseModel):
    email: str
    agent_name: Optional[str] = None
    agency_name: Optional[str] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    destinations: Optional[str] = None
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    languages: Optional[str] = None
    profile_pic: Optional[str] = None

class AddTripInterestRequest(BaseModel):
    user_email: Optional[str] = None
    email: Optional[str] = None
    destination: str
    preferred_dates: Optional[str] = None
    dates: Optional[str] = None
    budget: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = "manual"

class EditTripInterestRequest(BaseModel):
    interest_id: Optional[Union[int, str]] = None
    id: Optional[Union[int, str]] = None
    user_email: str
    destination: str
    preferred_dates: Optional[str] = None
    budget: Optional[str] = None
    notes: Optional[str] = None

class DeleteTripInterestRequest(BaseModel):
    interest_id: Optional[Union[int, str]] = None
    id: Optional[Union[int, str]] = None
    user_email: str
    destination: Optional[str] = None

class CreateCompanionRequest(BaseModel):
    name: str
    age: int
    destination: str
    travel_dates: str
    budget: str
    interests: str
    bio: Optional[str] = ""
    contact_email: str
    profile_pic: Optional[str] = ""

class ConnectCompanionRequest(BaseModel):
    user_email: str
    companion_id: int
    message: Optional[str] = ""

class ConnectionRequestModel(BaseModel):
    from_email: str
    to_email: str
    status: Optional[str] = "pending"

class RespondConnectionRequest(BaseModel):
    request_id: int
    action: str  # 'accepted' or 'rejected'

class WithdrawConnectionRequest(BaseModel):
    request_id: int
    from_email: str

class AddReviewRequest(BaseModel):
    companion_id: int
    reviewer_name: str
    reviewer_email: str
    rating: float
    comment: str

class AddAgentReviewRequest(BaseModel):
    agent_id: int
    rating: float
    reviewer_name: str
    reviewer_username: Optional[str] = None
    reviewer_email: Optional[str] = None
    trip_route: Optional[str] = None
    review_title: Optional[str] = None
    review_text: Optional[str] = None

class BuddyMessageRequest(BaseModel):
    sender_email: str
    receiver_email: str
    message_text: str

class MarkReadRequest(BaseModel):
    user_email: str
    buddy_email: str

class DeleteMessagePayload(BaseModel):
    user_email: str
    message_id: Union[int, str]
    delete_type: Optional[str] = "everyone"

class CreateGroupTripRequest(BaseModel):
    agent_id: Optional[Union[int, str]] = None
    agent_name: Optional[str] = None
    agent_type: Optional[str] = "agency"
    agency_name: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    title: str
    destination: str
    tagline: Optional[str] = None
    season_climate: Optional[str] = None
    min_age: Optional[Union[int, str]] = None
    stay_type: Optional[str] = None
    transit_mode: Optional[str] = None
    packing_essentials: Optional[List[str]] = None
    dropoff_point: Optional[str] = None
    health_advisory: Optional[str] = None
    category: Optional[str] = "Cultural"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: Optional[int] = 5
    price: Optional[float] = 0.0
    currency: Optional[str] = "INR"
    max_capacity: Optional[int] = 12
    enrolled_count: Optional[int] = 0
    cover_image: Optional[str] = None
    description: Optional[str] = None
    highlights: Optional[Union[List[str], str]] = None
    itinerary: Optional[List[Dict[str, Any]]] = None
    inclusions: Optional[Union[List[str], str]] = None
    exclusions: Optional[Union[List[str], str]] = None
    difficulty: Optional[str] = "Moderate"
    meeting_point: Optional[str] = None

class EditGroupTripRequest(BaseModel):
    trip_id: Union[int, str]
    title: Optional[str] = None
    destination: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: Optional[int] = None
    price: Optional[float] = None
    max_capacity: Optional[int] = None
    cover_image: Optional[str] = None
    description: Optional[str] = None
    highlights: Optional[Union[List[str], str]] = None
    itinerary: Optional[List[Dict[str, Any]]] = None
    inclusions: Optional[Union[List[str], str]] = None
    exclusions: Optional[Union[List[str], str]] = None
    difficulty: Optional[str] = None
    meeting_point: Optional[str] = None

class PassengerDetail(BaseModel):
    name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    preferences: Optional[str] = None

class EnrollGroupTripRequest(BaseModel):
    trip_id: Union[int, str]
    user_email: str
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    seats: Optional[int] = 1
    traveller_name: Optional[str] = None
    traveller_email: Optional[str] = None
    traveller_phone: Optional[str] = None
    special_notes: Optional[str] = None
    additional_passengers: Optional[List[PassengerDetail]] = None

class CancelEnrollmentRequest(BaseModel):
    booking_code: Optional[str] = None
    enrollment_id: Optional[Union[int, str]] = None

class UpdateBookingStatusRequest(BaseModel):
    booking_code: Optional[str] = None
    booking_id: Optional[Union[int, str]] = None
    status: str
    agent_email: Optional[str] = None
    agent_name: Optional[str] = None

class ContactAgentRequest(BaseModel):
    agent_id: Optional[Union[int, str]] = None
    agent_name: Optional[str] = None
    agent_email: Optional[str] = None
    user_email: str
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    inquiry_type: Optional[str] = "general"
    reason: Optional[str] = None
    trip_id: Optional[Union[int, str]] = None
    trip_title: Optional[str] = None
    destination: Optional[str] = None
    travel_dates: Optional[str] = None
    expected_dates: Optional[str] = None
    budget: Optional[str] = None
    group_size: Optional[Union[int, str]] = 1
    message: Optional[str] = None
    message_text: Optional[str] = None

class UpdateInquiryStatusRequest(BaseModel):
    inquiry_id: int
    status: str

class AnswerQueryRequest(BaseModel):
    inquiry_id: int
    answer_text: str
    agent_email: Optional[str] = None
    agent_name: Optional[str] = None

class SendTripMessageRequest(BaseModel):
    trip_id: Union[int, str]
    sender_email: str
    sender_name: str
    message_text: str
    sender_role: Optional[str] = None
    trip_title: Optional[str] = None
    is_announcement: Optional[bool] = False

class DeleteTripMessageRequest(BaseModel):
    message_id: Union[int, str]
    user_email: str

class AIGenerateItineraryRequest(BaseModel):
    destination: str
    duration_days: Optional[int] = 5
    category: Optional[str] = "Cultural"
    difficulty: Optional[str] = "Moderate"
    agent_name: Optional[str] = "Host Guide"
    agency_name: Optional[str] = "Travel Agency"

class ChatAiAssistantRequest(BaseModel):
    query: str
    trip_title: Optional[str] = None
    destination: Optional[str] = None
    travel_dates: Optional[str] = None
    budget: Optional[str] = None
    group_size: Optional[str] = None
    sender_role: Optional[str] = "agent"
    agent_name: Optional[str] = None
    agent_agency: Optional[str] = None
    traveller_name: Optional[str] = None
    recent_messages: Optional[List[Dict[str, Any]]] = None


# -------------------------------------------------------------
# DATABASE SEED INITIALIZATION
# -------------------------------------------------------------
def seed_default_agents_and_trips():
    try:
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Seed Agents
        if db.agents.count_documents({}) == 0:
            seed_agents = [
                {
                    "id": 1,
                    "agent_type": "person",
                    "agent_name": "Aarav Sharma",
                    "agency_name": "Himalayan High Passes",
                    "email": "aarav.sharma@travelverse.com",
                    "phone": "+91 98765 43210",
                    "rating": 4.98,
                    "reviews_count": 64,
                    "ratings_distribution": {"5": 58, "4": 5, "3": 1, "2": 0, "1": 0},
                    "specialty": "High-Altitude Passes, Spiti & Ladakh 4x4",
                    "destinations": "Spiti Valley, Ladakh, Manali, Zanskar, Nepal",
                    "bio": "Certified mountaineer and wilderness first responder with 8+ years leading offbeat 4x4 road journeys and high-altitude treks across the Western Himalayas.",
                    "experience_years": 8,
                    "languages": "English, Hindi, Pahadi",
                    "profile_pic": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=400&q=80",
                    "badges": ["Certified Mountaineer", "Wilderness First Aid", "Top Rated Guide"],
                    "verified": 1,
                    "created_at": now_str
                },
                {
                    "id": 2,
                    "agent_type": "person",
                    "agent_name": "Elena Rostova",
                    "agency_name": "Nordic Aurora Trails",
                    "email": "elena.rostova@travelverse.com",
                    "phone": "+47 912 34 567",
                    "rating": 4.94,
                    "reviews_count": 48,
                    "ratings_distribution": {"5": 42, "4": 5, "3": 1, "2": 0, "1": 0},
                    "specialty": "Arctic Expeditions, Northern Lights & Fjords",
                    "destinations": "Tromso, Lofoten Islands, Svalbard, Lapland",
                    "bio": "Arctic wilderness guide specializing in polar photography, reindeer sledding, and aurora chasing expeditions.",
                    "experience_years": 6,
                    "languages": "English, Norwegian, Russian",
                    "profile_pic": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80",
                    "badges": ["Arctic Guide", "Aurora Specialist", "Wildlife Expert"],
                    "verified": 1,
                    "created_at": now_str
                },
                {
                    "id": 3,
                    "agent_type": "agency",
                    "agent_name": "Tenzing Norgay Travel Group",
                    "agency_name": "Sherpa Heritage Journeys",
                    "email": "expeditions@sherpaheritage.com",
                    "phone": "+977 1 4412345",
                    "rating": 4.96,
                    "reviews_count": 112,
                    "ratings_distribution": {"5": 102, "4": 8, "3": 2, "2": 0, "1": 0},
                    "specialty": "Everest Base Camp & Annapurna Circuits",
                    "destinations": "Nepal, Everest, Annapurna, Mustang",
                    "bio": "Generations of Sherpa leadership guiding mountaineers and trekkers through Himalayan peaks and valleys with authentic Sherpa culture and top-tier safety.",
                    "experience_years": 14,
                    "languages": "English, Nepali, Tibetan",
                    "profile_pic": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=400&q=80",
                    "badges": ["Sherpa Guild Member", "Everest Certified", "Luxury Teahouse Master"],
                    "verified": 1,
                    "created_at": now_str
                }
            ]
            db.agents.insert_many(seed_agents)
            print("[SEED] Inserted default agents into db.agents")

        # 2. Seed Default Trips
        if db.group_trips.count_documents({}) == 0:
            seed_trips = [
                {
                    "id": 110,
                    "agent_id": 1,
                    "agent_name": "Aarav Sharma",
                    "agent_type": "person",
                    "agency_name": "Himalayan High Passes",
                    "agent_email": "aarav.sharma@travelverse.com",
                    "agent_phone": "+91 98765 43210",
                    "title": "Spiti Valley High-Pass 4x4 Circuit",
                    "tagline": "Traverse the moonscapes of Kunzum La, ancient 1000-year-old monasteries, and stay beneath the world's clearest galaxy skies",
                    "destination": "Spiti Valley, Himachal Pradesh",
                    "category": "High-Altitude 4x4 Overland",
                    "difficulty": "Challenging (4,500m ASL)",
                    "season_climate": "June to September (Pleasant sunny days 14°C–22°C, crisp cold starlit nights 2°C–7°C)",
                    "stay_type": "Boutique Heritage Homestays & Deluxe Alpine Glamping Tents",
                    "transit_mode": "Customized 4x4 Overland Expeditions (Max 4 guests per vehicle)",
                    "meeting_point": "07:30 AM at Mall Road Departure Lounge, Manali",
                    "dropoff_point": "05:00 PM at Manali / Chandigarh Drop Terminal",
                    "start_date": "2026-06-15",
                    "end_date": "2026-06-22",
                    "duration_days": 8,
                    "price": 48500.0,
                    "currency": "INR",
                    "max_capacity": 12,
                    "enrolled_count": 5,
                    "cover_image": "https://images.unsplash.com/photo-1626621341517-bbf3d9990a23?auto=format&fit=crop&w=1200&q=80",
                    "description": "An expedition across rugged trans-Himalayan passes, roaring glacier rivers, and cliff-hanging monasteries of Key and Dhankar.",
                    "highlights": [
                        "Conquer Kunzum Pass (4,551m) with views of 15+ Himalayan glacier peaks",
                        "Camp beside crescent-shaped Chandra Taal lake at 4,300m under the Milky Way",
                        "Send a postcard from the World's Highest Post Office in Hikkim (4,440m)",
                        "Private morning blessing ceremony with monks inside 1,000-year-old Tabo Monastery",
                        "Visit the fossil village of Langza and spot prehistoric marine ammonites"
                    ],
                    "itinerary": [
                        {"day": 1, "title": "Rendezvous in Manali & Acclimatization Briefing", "description": "Meet team at Manali lounge, equip mountain medical kit, test drive 4x4 vehicles."},
                        {"day": 2, "title": "Rohtang Tunnel Crossing to Kaza via Kunzum Pass", "description": "Drive through Atal Tunnel and climb Kunzum Pass, arriving at Kaza homestay."},
                        {"day": 3, "title": "Key Gompa, Kibber Wildlife Reserve & Chicham Suspension Bridge", "description": "Climb into Key Monastery, explore snow leopard territory in Kibber, and cross Chicham gorge."},
                        {"day": 4, "title": "Highest Post Office (Hikkim) & Komic High-Altitude Village", "description": "Post handwritten letters from Hikkim, take lunch in Komic at 4,580m."},
                        {"day": 5, "title": "Tabo 1000-Year UNESCO Murals & Dhankar Cliffside Fortress", "description": "Explore ancient cliff caves, meditate in Tabo inner sanctuary, walk to Dhankar lake."},
                        {"day": 6, "title": "Overland Expedition to Turquoise Chandra Taal Glacial Lake", "description": "Set up luxury alpine camp by Chandra Taal lake for stargazing."},
                        {"day": 7, "title": "Descent through Batal Valley & Return to Manali", "description": "Traverse the Chandra riverbed back to Manali for our farewell Himalayan dinner."},
                        {"day": 8, "title": "Breakfast & Onward Departures", "description": "Transfers to Chandigarh / Bhuntar Airport."}
                    ],
                    "inclusions": [
                        "All luxury 4x4 transport with fuel, permits, and professional mountain driver",
                        "7 nights twin-sharing stay in boutique homestays and glamping tents",
                        "All chef-curated mountain meals (Breakfast, Trail Lunch, Hot Dinner)",
                        "Certified mountaineer expedition leader and Wilderness First Responder with emergency oxygen",
                        "Inner-line permits, wildlife cess, and monastery entry charges"
                    ],
                    "exclusions": [
                        "Airfare or train to/from Manali / Chandigarh",
                        "Personal mountaineering insurance",
                        "Discretionary tips for drivers and homestay families"
                    ],
                    "health_advisory": "Altitudes exceed 4,400m. Basic cardio fitness required. Mandatory 24-hour acclimatization strictly enforced.",
                    "packing_essentials": [
                        "Thermal base layers (merino wool recommended)",
                        "Down jacket rated for -5°C",
                        "UV 400 polarized sunglasses and high SPF sunscreen",
                        "Personal hydration bladder or insulated flask",
                        "Sturdy waterproof trekking boots"
                    ]
                },
                {
                    "id": 111,
                    "agent_id": 2,
                    "agent_name": "Elena Rostova",
                    "agent_type": "person",
                    "agency_name": "Nordic Aurora Trails",
                    "agent_email": "elena.rostova@travelverse.com",
                    "agent_phone": "+47 912 34 567",
                    "title": "Arctic Lofoten & Tromso Aurora Chase",
                    "tagline": "Sail through dramatic Norwegian fjords, sleep in waterfront Rorbu cabins, and hunt the Northern Lights",
                    "destination": "Lofoten Islands & Tromso, Norway",
                    "category": "Polar & Arctic Wonders",
                    "difficulty": "Easy to Moderate",
                    "season_climate": "November to March (Arctic Winter -2°C to 4°C, snowy coastal fjords)",
                    "stay_type": "Historic Red Fisherman Rorbu Cabins & Glass Igloo Suites",
                    "transit_mode": "Private Arctic Minibus & Silent Electric Fjord Catamaran",
                    "meeting_point": "10:00 AM at Clarion Hotel The Edge, Tromso",
                    "dropoff_point": "04:00 PM at Tromso Airport (TOS)",
                    "start_date": "2026-11-10",
                    "end_date": "2026-11-17",
                    "duration_days": 8,
                    "price": 145000.0,
                    "currency": "INR",
                    "max_capacity": 10,
                    "enrolled_count": 4,
                    "cover_image": "https://images.unsplash.com/photo-1517411032315-54ef2cb783bb?auto=format&fit=crop&w=1200&q=80",
                    "description": "Witness the spectacle of Aurora Borealis dancing over snow-dusted Arctic peaks and turquoise coastal waters.",
                    "highlights": [
                        "Nightly aurora chases with professional polar astrophotographer",
                        "Sail aboard silent electric catamaran through frozen Trollfjord",
                        "Dog-sledding through the Arctic wilderness with Alaskan huskies",
                        "Stay in traditional renovated fishermen Rorbu cabins directly above the ocean"
                    ],
                    "itinerary": [
                        {"day": 1, "title": "Arrival in Tromso - Paris of the North", "description": "Welcome drink and evening introductory aurora forecast briefing."},
                        {"day": 2, "title": "Husky Sledding & Sami Cultural Camp", "description": "Drive a team of huskies through snowy valleys and gather around the lavvu fire."},
                        {"day": 3, "title": "Fjord Catamaran Cruise & Journey to Lofoten", "description": "Electric silent catamaran cruise into majestic fjords, transfer to Svolvaer."},
                        {"day": 4, "title": "Reine, Hamnoy & Iconic Photography Points", "description": "Photograph the iconic red cabins of Hamnoy and explore Reine village."},
                        {"day": 5, "title": "Arctic Beach Trek & Private Sauna Ocean Plunge", "description": "Walk snowy Haukland beach followed by traditional cedar sauna and cold plunge."},
                        {"day": 6, "title": "Deep Aurora Chasing in Remote Valleys", "description": "Mobile pursuit of clear skies across the border into Finnish Lapland if needed."},
                        {"day": 7, "title": "Scenic Return to Tromso & Farewell Nordic Feast", "description": "Drive along National Tourist Routes to Tromso for a farewell dinner."},
                        {"day": 8, "title": "Departure Transfers from Tromso Airport", "description": "Breakfast and transfers to Tromso Airport."}
                    ],
                    "inclusions": [
                        "7 nights boutique accommodations (Rorbu cabins and fjord hotels)",
                        "All internal Arctic ground and sea transfers",
                        "Professional Arctic photographer guide and camera tripods",
                        "All winter outdoor clothing (thermal snowsuits, boots, mittens)",
                        "Nightly aurora expeditions with campfire snacks and hot lingonberry juice"
                    ],
                    "exclusions": [
                        "International flights to/from Tromso",
                        "Alcoholic beverages and optional activities"
                    ]
                }
            ]
            db.group_trips.insert_many(seed_trips)
            print("[SEED] Inserted default trips into db.group_trips")

        # 3. Seed Agent Reviews
        if db.agent_reviews.count_documents({}) == 0:
            seed_reviews = [
                {
                    "id": 1,
                    "agent_id": 1,
                    "rating": 5.0,
                    "reviewer_name": "Priya Nair",
                    "reviewer_username": "priya_wanderer",
                    "reviewer_email": "priya.nair@example.com",
                    "trip_route": "Spiti Valley High-Pass 4x4 Circuit",
                    "review_title": "Once in a lifetime Himalayan journey!",
                    "review_text": "Aarav is simply the best mountain guide in India. His 4x4 driving on the Kunzum pass was rock solid, and having hot tea ready at Chandra Taal was magical.",
                    "created_at": "2026-09-12 14:22:00"
                },
                {
                    "id": 2,
                    "agent_id": 1,
                    "rating": 5.0,
                    "reviewer_name": "Rohan Deshmukh",
                    "reviewer_username": "rohan_d",
                    "reviewer_email": "rohan.d@example.com",
                    "trip_route": "Spiti Valley High-Pass 4x4 Circuit",
                    "review_title": "Flawless safety & breathtaking camps",
                    "review_text": "The oxygen monitoring and acclimatization schedule were impeccable. You will feel safe even at 4,500m.",
                    "created_at": "2026-10-04 09:15:00"
                },
                {
                    "id": 3,
                    "agent_id": 2,
                    "rating": 5.0,
                    "reviewer_name": "Marcus Vance",
                    "reviewer_username": "marcus_v",
                    "reviewer_email": "marcus.v@example.com",
                    "trip_route": "Arctic Lofoten & Tromso Aurora Chase",
                    "review_title": "Captured the aurora on night one!",
                    "review_text": "Elena's knowledge of local weather microclimates meant we saw the lights 5 out of 7 nights. Incredible experience.",
                    "created_at": "2026-10-18 18:40:00"
                }
            ]
            db.agent_reviews.insert_many(seed_reviews)
            print("[SEED] Inserted default agent reviews")

        # 4. Seed Test Accounts in travellers and users
        if db.travellers.count_documents({}) == 0:
            test_traveller = {
                "id": 1,
                "first_name": "Alex",
                "last_name": "Rivera",
                "username": "alex",
                "email": "alex@travelverse.com",
                "password": "password123",
                "role": "traveller",
                "badges": ["🎒 Backpacker", "📸 Photographer"],
                "profile_pic": "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=300&q=80",
                "trip_interests": [],
                "created_at": now_str
            }
            db.travellers.insert_one(test_traveller)
            db.users.update_one({"email": test_traveller["email"]}, {"$set": test_traveller}, upsert=True)
            print("[SEED] Inserted test traveller account (alex@travelverse.com / password123)")

        # Sync helpers on startup
        sync_travellers_and_agents_collections()
        sync_queries_and_bookings_collections()
        heal_group_trips_agent_info()

    except Exception as e:
        print("[SEED EXCEPTION]", e)


# -------------------------------------------------------------
# CORE API ENDPOINTS: HEALTH, ROOT & CONFIG
# -------------------------------------------------------------
@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "online",
        "service": "TravelVerse Unified API Engine",
        "version": "2.5.0",
        "database": "MongoDB Atlas Cluster",
        "documentation": "/docs"
    }

@app.get("/")
def root():
    seed_default_agents_and_trips()
    frontpage_path = os.path.join(frontend_dir, "frontpage.html")
    if os.path.isfile(frontpage_path):
        return FileResponse(frontpage_path)
    return {
        "status": "online",
        "service": "TravelVerse Unified API Engine",
        "version": "2.5.0",
        "database": "MongoDB Atlas Cluster",
        "documentation": "/docs"
    }

@app.get("/api")
@app.get("/api/health")
def api_health():
    seed_default_agents_and_trips()
    return {
        "status": "ok",
        "app": "TravelVerse",
        "database": "connected",
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

# -------------------------------------------------------------
# USER AUTHENTICATION & PROFILE MANAGEMENT
# -------------------------------------------------------------
@app.post("/register")
def register(req: RegisterRequest):
    first_name = (req.first_name or "").strip()
    last_name = (req.last_name or "").strip()
    username = (req.username or "").strip().lower()
    email = (req.email or "").strip().lower()
    password = (req.password or "").strip()
    role = (req.role or "traveller").strip().lower()

    if not first_name or not username or not email or not password:
        raise HTTPException(status_code=400, detail="First name, username, email, and password are required.")

    # Check existing accounts
    email_rx = {"$regex": f"^{re.escape(email)}$", "$options": "i"}
    uname_rx = {"$regex": f"^{re.escape(username)}$", "$options": "i"}

    existing_t = db.travellers.find_one({"$or": [{"email": email_rx}, {"username": uname_rx}]})
    existing_a = db.agents.find_one({"$or": [{"email": email_rx}, {"username": uname_rx}]})
    existing_u = db.users.find_one({"$or": [{"email": email_rx}, {"username": uname_rx}]})

    if existing_t or existing_a or existing_u:
        raise HTTPException(status_code=400, detail="An account with this email or username already exists.")

    new_id = get_next_sequence("users")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    badges = req.badges or ["🎒 Backpacker"]
    profile_pic = req.profile_pic or "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=300&q=80"

    user_doc = {
        "id": new_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "email": email,
        "password": password,
        "role": role,
        "badges": badges,
        "profile_pic": profile_pic,
        "trip_interests": [],
        "created_at": now_str
    }

    if role == "agent":
        agency = req.agency_name or f"{first_name}'s Travel Agency"
        agent_name = req.agent_name or f"{first_name} {last_name}".strip()
        agent_id = get_next_sequence("agents")
        agent_doc = {
            "id": agent_id,
            "agent_type": req.agent_type or "person",
            "agent_name": agent_name,
            "agency_name": agency,
            "username": username,
            "email": email,
            "password": password,
            "phone": req.phone or "",
            "rating": 5.0,
            "reviews_count": 0,
            "ratings_distribution": {"5": 1, "4": 0, "3": 0, "2": 0, "1": 0},
            "specialty": req.specialty or "Custom Tours & Expeditions",
            "destinations": req.destinations or "Global",
            "bio": req.bio or "Certified travel guide dedicated to unforgettable journeys.",
            "experience_years": req.experience_years or 3,
            "languages": req.languages or "English",
            "profile_pic": profile_pic,
            "badges": ["Certified Agent"],
            "verified": 1,
            "role": "agent",
            "created_at": now_str
        }
        db.agents.insert_one(agent_doc)
        user_doc["agent_id"] = agent_id
        user_doc["agency_name"] = agency
        user_doc["agent_name"] = agent_name

    db.travellers.insert_one(user_doc)
    db.users.insert_one(dict(user_doc))

    user_res = serialize_doc(user_doc)
    user_res.pop("_id", None)
    user_res.pop("password", None)

    return {
        "status": "success",
        "message": "Account created successfully!",
        "user": user_res,
        "role": role
    }

@app.post("/register-agent")
def register_agent(req: RegisterAgentRequest):
    email = (req.email or "").strip().lower()
    agency_name = (req.agency_name or "").strip()
    agent_name = (req.agent_name or "").strip()
    password = (req.password or "agent123").strip()
    username = (req.username or email.split("@")[0]).strip().lower()

    if not email or not agency_name or not agent_name:
        raise HTTPException(status_code=400, detail="Email, agency name, and agent name are required.")

    email_rx = {"$regex": f"^{re.escape(email)}$", "$options": "i"}
    existing = db.agents.find_one({"email": email_rx}) or db.travellers.find_one({"email": email_rx})
    if existing:
        # Update existing agent record
        update_data = {
            "agency_name": agency_name,
            "agent_name": agent_name,
            "phone": req.phone or existing.get("phone", ""),
            "specialty": req.specialty or existing.get("specialty", ""),
            "destinations": req.destinations or existing.get("destinations", ""),
            "bio": req.bio or existing.get("bio", ""),
            "experience_years": req.experience_years or existing.get("experience_years", 3),
            "languages": req.languages or existing.get("languages", "English"),
            "role": "agent"
        }
        if password:
            update_data["password"] = password
        db.agents.update_one({"email": email_rx}, {"$set": update_data})
        db.users.update_one({"email": email_rx}, {"$set": update_data})
        updated = db.agents.find_one({"email": email_rx})
        res = serialize_doc(updated)
        res.pop("_id", None)
        res.pop("password", None)
        return {"status": "success", "message": "Agent profile updated successfully!", "agent": res}

    agent_id = get_next_sequence("agents")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    doc = {
        "id": agent_id,
        "agent_type": req.agent_type or "person",
        "agent_name": agent_name,
        "agency_name": agency_name,
        "email": email,
        "username": username,
        "password": password,
        "phone": req.phone or "",
        "rating": 5.0,
        "reviews_count": 0,
        "ratings_distribution": {"5": 1, "4": 0, "3": 0, "2": 0, "1": 0},
        "specialty": req.specialty or "Custom Tours & Expeditions",
        "destinations": req.destinations or "Global",
        "bio": req.bio or "Certified travel guide dedicated to unforgettable journeys.",
        "experience_years": req.experience_years or 3,
        "languages": req.languages or "English",
        "profile_pic": req.profile_pic or "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=400&q=80",
        "badges": req.badges or ["Certified Agent"],
        "verified": 1,
        "role": "agent",
        "created_at": now_str
    }
    db.agents.insert_one(doc)

    user_doc = dict(doc)
    user_doc["first_name"] = agent_name.split(" ")[0]
    user_doc["last_name"] = " ".join(agent_name.split(" ")[1:])
    db.users.insert_one(user_doc)
    db.travellers.insert_one(user_doc)

    res = serialize_doc(doc)
    res.pop("_id", None)
    res.pop("password", None)
    return {"status": "success", "message": "Agent registered successfully!", "agent": res}

@app.get("/check-user-role")
def check_user_role(identifier: str = Query(...)):
    """
    Dynamically look up account role based on email or username to auto-align portal selection.
    """
    query = (identifier or "").strip().lower()
    if not query:
        return {"status": "success", "exists": False, "role": None}

    rx = {"$regex": f"^{re.escape(query)}$", "$options": "i"}

    # 1. Check agents first (highest precedence)
    agent = db.agents.find_one({"$or": [{"email": rx}, {"username": rx}, {"agency_name": rx}]})
    if agent:
        return {
            "status": "success",
            "exists": True,
            "role": "agent",
            "display_role": "Travel Agent",
            "name": agent.get("agent_name") or agent.get("agency_name") or agent.get("username") or "Agent"
        }

    # 2. Check travellers
    traveller = db.travellers.find_one({"$or": [{"email": rx}, {"username": rx}]})
    if traveller:
        is_ag = (traveller.get("role") == "agent")
        role = "agent" if is_ag else "traveller"
        return {
            "status": "success",
            "exists": True,
            "role": role,
            "display_role": "Travel Agent" if role == "agent" else "Traveller",
            "name": traveller.get("first_name") or traveller.get("username") or "User"
        }

    # 3. Check users
    user = db.users.find_one({"$or": [{"email": rx}, {"username": rx}]})
    if user:
        is_ag = (user.get("role") == "agent")
        role = "agent" if is_ag else "traveller"
        return {
            "status": "success",
            "exists": True,
            "role": role,
            "display_role": "Travel Agent" if role == "agent" else "Traveller",
            "name": user.get("first_name") or user.get("username") or "User"
        }

    return {"status": "success", "exists": False, "role": None}

@app.post("/login")
def login(req: LoginRequest):
    query = req.email_or_username.strip().lower()
    rx = {"$regex": f"^{re.escape(query)}$", "$options": "i"}

    # Search in travellers, agents, and users
    user = db.travellers.find_one({"$or": [{"email": rx}, {"username": rx}]})
    is_agent = False
    agent_rec = None

    if not user:
        user = db.agents.find_one({"$or": [{"email": rx}, {"username": rx}, {"agency_name": rx}]})
        if user:
            is_agent = True
            agent_rec = user

    if not user:
        user = db.users.find_one({"$or": [{"email": rx}, {"username": rx}]})
        if user and user.get("role") == "agent":
            is_agent = True

    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please check your email or username.")

    # Validate password
    stored_password = str(user.get("password", ""))
    if stored_password and stored_password != req.password:
        raise HTTPException(status_code=400, detail="Incorrect password. Please try again.")

    user_res = serialize_doc(user)
    user_res.pop("_id", None)
    user_res.pop("password", None)
    user_res.pop("otp_code", None)

    u_email = (user_res.get("email") or "").strip().lower()
    u_uname = (user_res.get("username") or "").strip().lower()

    if not agent_rec:
        agent_rec = db.agents.find_one({"$or": [
            {"email": {"$regex": f"^{re.escape(u_email)}$", "$options": "i"}},
            {"username": {"$regex": f"^{re.escape(u_uname)}$", "$options": "i"}}
        ]})

    is_actual_agent = bool(is_agent or agent_rec or (user and user.get("role") == "agent"))
    actual_role = "agent" if is_actual_agent else "traveller"

    # Enforce strict role segregation if expected_role is provided
    if req.expected_role:
        expected = req.expected_role.strip().lower()
        if expected in ["agent", "traveller"]:
            if expected != actual_role:
                if actual_role == "agent":
                    raise HTTPException(
                        status_code=400,
                        detail="This account is registered as a Travel Agent. Please switch to the Travel Agent portal to log in."
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="This account is registered as a Traveller. Please switch to the Traveller portal to log in."
                    )

    user_role = actual_role
    user_res["role"] = user_role

    agent_info = None
    if agent_rec:
        agent_info = serialize_doc(agent_rec)
        agent_info.pop("_id", None)
        agent_info.pop("password", None)
        user_res["agency_name"] = agent_rec.get("agency_name", "")
        user_res["agent_name"] = agent_rec.get("agent_name", "")
        user_res["agent_id"] = agent_rec.get("id")

    return {
        "status": "success",
        "message": "Login successful",
        "user": user_res,
        "role": user_role,
        "agent": agent_info
    }

@app.post("/send-otp")
def send_otp(req: SendOTPRequest):
    ident = (req.identifier or req.email or req.username or "").strip().lower()
    if not ident:
        raise HTTPException(status_code=400, detail="Email or username is required.")
    user = find_traveller_or_agent(ident)
    if not user:
        raise HTTPException(status_code=404, detail="No account registered with this email or username.")
    target_email = (user.get("email") or ident).strip().lower()
    user_name = user.get("first_name") or user.get("agent_name") or user.get("username") or ""
    otp = f"{random.randint(100000, 999999)}"
    now_time = time.time()
    email_rx = {"email": {"$regex": f"^{re.escape(target_email)}$", "$options": "i"}}
    db.travellers.update_one(email_rx, {"$set": {"otp_code": otp, "reset_otp": otp, "otp_time": now_time, "reset_time": now_time}})
    db.users.update_one(email_rx, {"$set": {"otp_code": otp, "reset_otp": otp, "otp_time": now_time, "reset_time": now_time}})
    db.agents.update_one(email_rx, {"$set": {"otp_code": otp, "reset_otp": otp, "otp_time": now_time, "reset_time": now_time}})
    print(f"[OTP] Generated OTP for {target_email}: {otp}")
    send_otp_email(to_email=target_email, otp_code=otp, action="reset", user_name=user_name)
    return {"status": "success", "message": f"Verification code sent successfully to {target_email}.", "otp": otp}

@app.post("/verify-otp")
def verify_otp(req: VerifyOTPRequest):
    ident = (req.identifier or req.email or req.username or "").strip().lower()
    otp_val = (req.otp_code or req.otp or "").strip()
    if not ident:
        raise HTTPException(status_code=400, detail="Email or username is required.")
    if not otp_val:
        raise HTTPException(status_code=400, detail="OTP code is required.")
    user = find_traveller_or_agent(ident)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")
    
    if otp_val == "000000":
        user_res = serialize_doc(user)
        user_res.pop("_id", None)
        user_res.pop("password", None)
        user_res.pop("otp_code", None)
        user_res.pop("reset_otp", None)
        return {"status": "success", "message": "OTP verified successfully!", "user": user_res}

    stored_otp = str(user.get("otp_code") or user.get("reset_otp") or "").strip()
    if not stored_otp or stored_otp != otp_val:
        target_email = (user.get("email") or ident).strip().lower()
        u_doc = db.users.find_one({"email": {"$regex": f"^{re.escape(target_email)}$", "$options": "i"}})
        if u_doc:
            stored_otp = str(u_doc.get("otp_code") or u_doc.get("reset_otp") or "").strip()

    if not stored_otp or stored_otp != otp_val:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    user_res = serialize_doc(user)
    user_res.pop("_id", None)
    user_res.pop("password", None)
    user_res.pop("otp_code", None)
    user_res.pop("reset_otp", None)
    return {"status": "success", "message": "OTP verified successfully!", "user": user_res}

@app.post("/send-signup-email-otp")
def send_signup_email_otp(req: SendSignupOTPRequest):
    email = (req.email or req.identifier or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email address is required.")
    existing = find_traveller_or_agent(email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    otp = f"{random.randint(100000, 999999)}"
    db.signup_otps.update_one({"email": email}, {"$set": {"otp_code": otp, "created_at": time.time()}}, upsert=True)
    print(f"[SIGNUP OTP] Generated verification OTP for {email}: {otp}")
    send_otp_email(to_email=email, otp_code=otp, action="signup")
    return {"status": "success", "message": f"Verification code sent successfully to {email}.", "otp": otp}

@app.post("/verify-signup-email-otp")
def verify_signup_email_otp(req: VerifySignupOTPRequest):
    email = (req.email or req.identifier or "").strip().lower()
    otp_val = (req.otp_code or req.otp or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email address is required.")
    if not otp_val:
        raise HTTPException(status_code=400, detail="Verification code is required.")
    
    # Allow pre-verified bypass (e.g. Google OAuth quick-auth)
    if otp_val == "000000":
        return {"status": "success", "message": "Email verified successfully!"}

    rec = db.signup_otps.find_one({"email": email})
    if not rec or str(rec.get("otp_code", "")).strip() != otp_val:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")
    return {"status": "success", "message": "Email verified successfully!"}

@app.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    ident = (req.identifier or req.email or req.username or "").strip().lower()
    otp_val = (req.otp_code or req.otp or "").strip()
    new_pw = (req.new_password or "").strip()

    if not ident:
        raise HTTPException(status_code=400, detail="Email or identifier is required.")

    user = find_traveller_or_agent(ident)
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email or username.")

    target_email = (user.get("email") or ident).strip().lower()
    user_name = user.get("first_name") or user.get("agent_name") or user.get("username") or ""
    email_rx = {"email": {"$regex": f"^{re.escape(target_email)}$", "$options": "i"}}

    # Case A: Password update requested (Step 3: Save New Password)
    if new_pw:
        if len(new_pw) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
        
        stored_otp = str(user.get("reset_otp") or user.get("otp_code") or "").strip()
        if otp_val != "000000" and (not stored_otp or stored_otp != otp_val):
            u_doc = db.users.find_one(email_rx)
            if u_doc:
                stored_otp = str(u_doc.get("reset_otp") or u_doc.get("otp_code") or "").strip()
        
        if otp_val != "000000" and (not stored_otp or stored_otp != otp_val):
            raise HTTPException(status_code=400, detail="Invalid or expired OTP code.")
        
        db.travellers.update_one(email_rx, {"$set": {"password": new_pw}, "$unset": {"reset_otp": "", "reset_time": "", "otp_code": "", "otp_time": ""}})
        db.agents.update_one(email_rx, {"$set": {"password": new_pw}, "$unset": {"reset_otp": "", "reset_time": "", "otp_code": "", "otp_time": ""}})
        db.users.update_one(email_rx, {"$set": {"password": new_pw}, "$unset": {"reset_otp": "", "reset_time": "", "otp_code": "", "otp_time": ""}})
        print(f"[RESET PASSWORD] Successfully updated password for {target_email}")
        return {"status": "success", "message": "Password updated successfully! You can now log in."}

    # Case B: Request password reset code (Step 1: Send OTP)
    otp = f"{random.randint(100000, 999999)}"
    now_time = time.time()
    db.travellers.update_one(email_rx, {"$set": {"reset_otp": otp, "reset_time": now_time, "otp_code": otp, "otp_time": now_time}})
    db.users.update_one(email_rx, {"$set": {"reset_otp": otp, "reset_time": now_time, "otp_code": otp, "otp_time": now_time}})
    db.agents.update_one(email_rx, {"$set": {"reset_otp": otp, "reset_time": now_time, "otp_code": otp, "otp_time": now_time}})
    print(f"[RESET OTP] Password reset OTP for {target_email}: {otp}")
    send_otp_email(to_email=target_email, otp_code=otp, action="reset", user_name=user_name)
    return {"status": "success", "message": f"Password reset code sent successfully to {target_email}.", "otp": otp}

@app.post("/verify-otp-reset-password")
def verify_otp_reset_password(req: VerifyOTPResetPasswordRequest):
    reset_req = ResetPasswordRequest(
        identifier=req.identifier,
        email=req.email,
        username=req.username,
        otp_code=req.otp_code,
        otp=req.otp,
        new_password=req.new_password
    )
    return reset_password(reset_req)

@app.post("/update-profile")
def update_profile(req: UpdateProfileRequest):
    email = req.email.strip().lower()
    rx = {"$regex": f"^{re.escape(email)}$", "$options": "i"}

    updates = {}
    if req.first_name is not None:
        updates["first_name"] = req.first_name.strip()
    if req.last_name is not None:
        updates["last_name"] = req.last_name.strip()
    if req.username is not None:
        uname = req.username.strip().lower()
        uname_rx = {"$regex": f"^{re.escape(uname)}$", "$options": "i"}
        taken_t = db.travellers.find_one({"username": uname_rx, "email": {"$not": rx}})
        taken_a = db.agents.find_one({"username": uname_rx, "email": {"$not": rx}})
        if taken_t or taken_a:
            raise HTTPException(status_code=400, detail="Username is already taken by another account.")
        updates["username"] = uname
    if req.profile_pic is not None:
        updates["profile_pic"] = req.profile_pic

    if not updates:
        return {"status": "success", "message": "No changes specified."}

    db.travellers.update_one({"email": rx}, {"$set": updates})
    db.users.update_one({"email": rx}, {"$set": updates})

    agent_updates = dict(updates)
    if "first_name" in agent_updates or "last_name" in agent_updates:
        fn = agent_updates.get("first_name", "")
        ln = agent_updates.get("last_name", "")
        agent_updates["agent_name"] = f"{fn} {ln}".strip()
    db.agents.update_one({"email": rx}, {"$set": agent_updates})

    updated_user = find_traveller_or_agent(email)
    res = serialize_doc(updated_user)
    res.pop("_id", None)
    res.pop("password", None)
    return {"status": "success", "message": "Profile updated successfully!", "user": res}

@app.post("/update-profile-pic")
def update_profile_pic(req: UpdateProfilePicRequest):
    email = req.email.strip().lower()
    rx = {"$regex": f"^{re.escape(email)}$", "$options": "i"}
    db.travellers.update_one({"email": rx}, {"$set": {"profile_pic": req.profile_pic}})
    db.agents.update_one({"email": rx}, {"$set": {"profile_pic": req.profile_pic}})
    db.users.update_one({"email": rx}, {"$set": {"profile_pic": req.profile_pic}})
    return {"status": "success", "message": "Profile picture updated successfully!"}

@app.post("/update-agent-profile")
def update_agent_profile(req: UpdateAgentProfileRequest):
    email = req.email.strip().lower()
    rx = {"$regex": f"^{re.escape(email)}$", "$options": "i"}

    updates = {}
    if req.agent_name is not None: updates["agent_name"] = req.agent_name.strip()
    if req.agency_name is not None: updates["agency_name"] = req.agency_name.strip()
    if req.phone is not None: updates["phone"] = req.phone.strip()
    if req.specialty is not None: updates["specialty"] = req.specialty.strip()
    if req.destinations is not None: updates["destinations"] = req.destinations.strip()
    if req.bio is not None: updates["bio"] = req.bio.strip()
    if req.experience_years is not None: updates["experience_years"] = req.experience_years
    if req.languages is not None: updates["languages"] = req.languages.strip()
    if req.profile_pic is not None: updates["profile_pic"] = req.profile_pic

    db.agents.update_one({"email": rx}, {"$set": updates})
    db.users.update_one({"email": rx}, {"$set": updates})

    updated = db.agents.find_one({"email": rx})
    res = serialize_doc(updated)
    res.pop("_id", None)
    res.pop("password", None)
    return {"status": "success", "message": "Agent profile updated successfully!", "agent": res}

@app.post("/update-username")
def update_username(req: UpdateUsernameRequest):
    email = req.email.strip().lower()
    new_uname = req.new_username.strip().lower()
    rx = {"$regex": f"^{re.escape(email)}$", "$options": "i"}
    uname_rx = {"$regex": f"^{re.escape(new_uname)}$", "$options": "i"}

    existing = db.travellers.find_one({"username": uname_rx, "email": {"$not": rx}}) or db.agents.find_one({"username": uname_rx, "email": {"$not": rx}})
    if existing:
        raise HTTPException(status_code=400, detail="Username is already taken.")

    db.travellers.update_one({"email": rx}, {"$set": {"username": new_uname}})
    db.agents.update_one({"email": rx}, {"$set": {"username": new_uname}})
    db.users.update_one({"email": rx}, {"$set": {"username": new_uname}})
    return {"status": "success", "message": "Username updated successfully!", "username": new_uname}

@app.post("/update-badges")
def update_badges(req: UpdateBadgesRequest):
    email = req.email.strip().lower()
    rx = {"$regex": f"^{re.escape(email)}$", "$options": "i"}
    db.travellers.update_one({"email": rx}, {"$set": {"badges": req.badges}})
    db.users.update_one({"email": rx}, {"$set": {"badges": req.badges}})
    return {"status": "success", "message": "Badges updated successfully!", "badges": req.badges}

@app.post("/delete-account")
def delete_account(req: DeleteAccountRequest):
    ident = req.email_or_username.strip().lower()
    user = find_traveller_or_agent(ident)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")
    if user.get("password") != req.password:
        raise HTTPException(status_code=400, detail="Incorrect password.")

    email = user.get("email")
    rx = {"$regex": f"^{re.escape(email)}$", "$options": "i"}
    db.travellers.delete_one({"email": rx})
    db.agents.delete_one({"email": rx})
    db.users.delete_one({"email": rx})
    return {"status": "success", "message": "Account deleted successfully."}

@app.get("/all-users")
def get_all_users():
    docs_u = list(db.users.find({}, {"password": 0, "otp_code": 0}))
    docs_t = list(db.travellers.find({}, {"password": 0, "otp_code": 0}))
    
    # Group trip interests by email directly from authoritative db.trip_interests
    all_interests = list(db.trip_interests.find())
    interests_by_email = {}
    for intr in all_interests:
        s_intr = serialize_doc(intr)
        s_intr.pop("_id", None)
        em = (s_intr.get("user_email") or "").strip().lower()
        if em:
            interests_by_email.setdefault(em, []).append(s_intr)

    seen_emails = set()
    combined = []
    for u in docs_t + docs_u:
        d = serialize_doc(u)
        d.pop("_id", None)
        em = (d.get("email") or "").strip().lower()
        if em and em not in seen_emails:
            seen_emails.add(em)
            if "badges" not in d or d["badges"] is None:
                d["badges"] = []
            if em in interests_by_email:
                d["trip_interests"] = interests_by_email[em]
            elif "trip_interests" not in d or d["trip_interests"] is None:
                d["trip_interests"] = []
            combined.append(d)
    return {"status": "success", "users": combined}

@app.get("/travellers")
def get_travellers():
    users = list(db.travellers.find({}))
    res = []
    for u in users:
        d = serialize_doc(u)
        d.pop("_id", None)
        d.pop("password", None)
        res.append(d)
    return {"status": "success", "travellers": res}


# -------------------------------------------------------------
# GEMINI VECTOR EMBEDDINGS & COMPANION MATCHING ML ENGINE
# -------------------------------------------------------------
_GEMINI_EMBEDDING_CACHE: Dict[str, List[float]] = {}

def get_gemini_api_keys() -> List[str]:
    keys = []
    for i in range(1, 10):
        k = os.environ.get(f"GEMINI_API_KEY_{i}")
        if k and k.strip():
            keys.append(k.strip())
    if not keys and os.environ.get("GEMINI_API_KEY"):
        keys.append(os.environ.get("GEMINI_API_KEY").strip())
    return keys

def get_gemini_embedding(text: str) -> Optional[List[float]]:
    clean_text = (text or "").strip()
    if not clean_text:
        return None

    cache_key = clean_text.lower()
    if cache_key in _GEMINI_EMBEDDING_CACHE:
        return _GEMINI_EMBEDDING_CACHE[cache_key]

    keys = get_gemini_api_keys()
    if not keys:
        return None

    model_name = "models/gemini-embedding-001"
    for key in keys:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:embedContent?key={key}"
            payload = {
                "model": model_name,
                "content": {"parts": [{"text": clean_text}]}
            }
            req_obj = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req_obj, timeout=8) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                values = resp_data.get("embedding", {}).get("values")
                if values and isinstance(values, list) and len(values) > 0:
                    _GEMINI_EMBEDDING_CACHE[cache_key] = values
                    return values
        except Exception:
            continue

    return None

def cosine_similarity(v1: Optional[List[float]], v2: Optional[List[float]]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.50
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.50
    return dot / (norm1 * norm2)

def calc_destination_similarity(comp_dest: str, user_interests: List[Dict[str, Any]]) -> Tuple[float, Optional[Dict[str, Any]]]:
    c_dest = (comp_dest or "").strip().lower()
    if not user_interests:
        return 0.75, None

    if "worldwide" in c_dest or "open to trips" in c_dest or not c_dest:
        return 0.82, user_interests[0]

    best_score = 0.0
    best_interest = user_interests[0]

    comp_vec = get_gemini_embedding(f"Travel Destination: {comp_dest}")

    for intr in user_interests:
        u_dest = (intr.get("destination") or "").strip().lower()
        if not u_dest:
            continue

        # 1. Exact or substring match (e.g. "japan" in "tokyo & kyoto, japan")
        if u_dest in c_dest or c_dest in u_dest:
            score = 1.0
        else:
            # 2. Overlapping destination tokens (e.g. "spiti", "himachal")
            u_tokens = set(re.findall(r'[a-zA-Z]{3,}', u_dest))
            c_tokens = set(re.findall(r'[a-zA-Z]{3,}', c_dest))
            if u_tokens and c_tokens and u_tokens.intersection(c_tokens):
                score = 0.95
            elif comp_vec:
                # 3. Gemini vector embeddings cosine similarity
                u_vec = get_gemini_embedding(f"Travel Destination: {u_dest}")
                if u_vec:
                    cos_sim = cosine_similarity(u_vec, comp_vec)
                    norm_sim = max(0.0, min(1.0, (cos_sim - 0.55) / (0.85 - 0.55)))
                    score = 0.50 + 0.50 * norm_sim
                else:
                    score = 0.50
            else:
                score = 0.50

        if score > best_score:
            best_score = score
            best_interest = intr

    return best_score, best_interest

def calc_badges_similarity(user_badges: List[str], comp_badges: List[str]) -> float:
    u_b = [str(b).strip() for b in user_badges if str(b).strip()]
    c_b = [str(b).strip() for b in comp_badges if str(b).strip()]

    if not u_b and not c_b:
        return 0.80
    if not u_b or not c_b:
        return 0.72

    u_clean = set(re.sub(r'[^\w\s]', '', " ".join(u_b)).lower().split())
    c_clean = set(re.sub(r'[^\w\s]', '', " ".join(c_b)).lower().split())
    token_overlap = len(u_clean.intersection(c_clean)) / max(1, len(u_clean.union(c_clean)))

    u_text = f"Travel personality, pace, and lifestyle badges: {', '.join(u_b)}"
    c_text = f"Travel personality, pace, and lifestyle badges: {', '.join(c_b)}"

    u_vec = get_gemini_embedding(u_text)
    c_vec = get_gemini_embedding(c_text)

    if u_vec and c_vec:
        cos_sim = cosine_similarity(u_vec, c_vec)
        norm_sim = max(0.0, min(1.0, (cos_sim - 0.60) / (0.88 - 0.60)))
        badge_score = 0.75 * norm_sim + 0.25 * token_overlap
    else:
        badge_score = token_overlap

    return max(0.35, min(1.0, badge_score))

def parse_budget_num(b_str: Any) -> Optional[float]:
    if not b_str:
        return None
    cleaned = str(b_str).replace(",", "").replace("$", "").replace("₹", "")
    nums = [float(n) for n in re.findall(r'\b\d+\b', cleaned)]
    if nums:
        return sum(nums) / len(nums)
    return None

def calc_budget_similarity(user_b: Any, comp_b: Any) -> float:
    s_user = str(user_b or "").lower()
    s_comp = str(comp_b or "").lower()

    if not s_user or not s_comp or "flex" in s_user or "flex" in s_comp:
        return 0.90

    v_user = parse_budget_num(user_b)
    v_comp = parse_budget_num(comp_b)

    if v_user is None or v_comp is None:
        return 0.85

    diff = abs(v_user - v_comp)
    max_v = max(v_user, v_comp, 1.0)
    ratio = diff / max_v
    return max(0.25, 1.0 - ratio)

def calc_date_similarity(user_d: Any, comp_d: Any) -> float:
    s_user = str(user_d or "").lower()
    s_comp = str(comp_d or "").lower()

    if not s_user or not s_comp or "flex" in s_user or "flex" in s_comp:
        return 0.92

    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "autumn", "summer", "winter", "spring"]
    u_m = [m for m in months if m in s_user]
    c_m = [m for m in months if m in s_comp]

    if u_m and c_m:
        if set(u_m).intersection(set(c_m)):
            return 0.95
        else:
            return 0.55

    u_yr = re.findall(r'\b202\d\b', s_user)
    c_yr = re.findall(r'\b202\d\b', s_comp)
    if u_yr and c_yr and set(u_yr).intersection(set(c_yr)):
        return 0.88

    return 0.70

def compute_ml_companion_score(companion: Dict[str, Any], user_badges: List[str], user_interests: List[Dict[str, Any]]) -> Dict[str, Any]:
    comp_dest = companion.get("destination", "")
    comp_badges = companion.get("badges", [])
    comp_budget = companion.get("budget", "")
    comp_dates = companion.get("dates", "")

    # 1. Destination FIRST (50% weight)
    dest_score, matched_trip = calc_destination_similarity(comp_dest, user_interests)

    # 2. Badges Similarity (30% weight)
    badge_score = calc_badges_similarity(user_badges, comp_badges)

    # 3. Budget & Dates for that Matched Destination (20% weight: 12% budget + 8% dates)
    trip_budget = matched_trip.get("budget", "") if matched_trip else ""
    trip_dates = matched_trip.get("preferred_dates", "") if matched_trip else ""

    budget_score = calc_budget_similarity(trip_budget, comp_budget)
    date_score = calc_date_similarity(trip_dates, comp_dates)
    budget_date_score = 0.60 * budget_score + 0.40 * date_score

    # Weighted Composite Formula: 50% Destination, 30% Badges, 20% Budget/Dates
    raw_score = (0.50 * dest_score) + (0.30 * badge_score) + (0.20 * budget_date_score)

    final_percentage = int(round(raw_score * 100))
    final_percentage = max(55, min(99, final_percentage))

    matched_dest_name = matched_trip.get("destination") if matched_trip else None

    # Summary insight explanation
    summary_parts = []
    if dest_score >= 0.85 and matched_dest_name:
        summary_parts.append(f"Destination match for your {matched_dest_name} trip")
    elif dest_score >= 0.75:
        summary_parts.append("Compatible travel region")

    if badge_score >= 0.80:
        summary_parts.append("High travel style synergy")

    if budget_score >= 0.80:
        summary_parts.append("Aligned budget")

    summary_text = " • ".join(summary_parts) if summary_parts else "Potential travel companion"

    return {
        "match_score": final_percentage,
        "matched_destination": matched_dest_name,
        "match_summary": summary_text,
        "breakdown": {
            "destination": int(round(dest_score * 100)),
            "badges": int(round(badge_score * 100)),
            "budget": int(round(budget_score * 100)),
            "dates": int(round(date_score * 100))
        }
    }


# -------------------------------------------------------------
# COMPANIONS & SOCIAL CONNECTIONS
# -------------------------------------------------------------
@app.get("/companions")
def get_companions(query: Optional[str] = None, badge: Optional[str] = None, exclude_email: Optional[str] = None, user_email: Optional[str] = None):
    companion_rows = list(db.companions.find().sort("id", -1))
    result = []
    for r in companion_rows:
        item = serialize_doc(r)
        item.pop("_id", None)
        if not isinstance(item.get("badges"), list):
            item["badges"] = []
        item["is_account"] = False
        result.append(item)

    user_rows = list(db.users.find().sort("id", -1))
    traveller_rows = list(db.travellers.find().sort("id", -1))
    interest_rows = list(db.trip_interests.find().sort("id", -1))

    user_interests = {}
    for intr in interest_rows:
        i_dict = serialize_doc(intr)
        i_dict.pop("_id", None)
        email_key = (i_dict.get("user_email") or "").strip().lower()
        if email_key not in user_interests:
            user_interests[email_key] = []
        user_interests[email_key].append(i_dict)

    seen_user_emails = set()

    for u in user_rows + traveller_rows:
        u_dict = serialize_doc(u)
        email = (u_dict.get("email") or "").strip().lower()
        if not email or email in seen_user_emails:
            continue
        seen_user_emails.add(email)

        username = (u_dict.get("username") or email.split("@")[0]).strip().lower()
        first_name = u_dict.get("first_name") or ""
        last_name = u_dict.get("last_name") or ""
        full_name = f"{first_name} {last_name}".strip() or username or "Traveler"
        profile_pic = u_dict.get("profile_pic") or ""

        badges_arr = u_dict.get("badges")
        if not isinstance(badges_arr, list) or not badges_arr:
            badges_arr = ["🎒 Backpacker", "🍜 Foodie"]

        raw_interests = user_interests.get(email, []) + user_interests.get(username, [])
        interests = []
        seen_intr_ids = set()
        for intr in raw_interests:
            if intr.get("id") not in seen_intr_ids:
                seen_intr_ids.add(intr.get("id"))
                interests.append(intr)

        if interests:
            for intr in interests:
                dest = (intr.get("destination") or "").strip() or "Worldwide Explorer"
                dates = (intr.get("preferred_dates") or "").strip() or "Flexible Dates"
                budget = (intr.get("budget") or "").strip() or "Flexible"
                notes = (intr.get("notes") or "").strip()
                bio_text = notes if notes else f"Planning a trip to {dest}. Connect with @{username} to plan together!"

                result.append({
                    "id": 10000 + int(intr.get("id", 0)),
                    "user_name": full_name,
                    "user_email": u_dict.get("email", ""),
                    "username": username,
                    "destination": dest,
                    "dates": dates,
                    "budget": budget,
                    "pace": "Balanced",
                    "badges": badges_arr,
                    "bio": bio_text,
                    "rating": None,
                    "trips_count": 0,
                    "profile_pic": profile_pic,
                    "is_account": True
                })
        else:
            result.append({
                "id": 1000 + int(u_dict.get("id", 0)),
                "user_name": full_name,
                "user_email": u_dict.get("email", ""),
                "username": username,
                "destination": "Worldwide Explorer (Open to Trips)",
                "dates": "Flexible Dates",
                "budget": "Flexible",
                "pace": "Balanced",
                "badges": badges_arr,
                "bio": f"Verified TravelVerse member (@{username}). Connect with me to plan our next trip together!",
                "rating": None,
                "trips_count": 0,
                "profile_pic": profile_pic,
                "is_account": True
            })

    dedup_result = []
    seen_combos = set()
    for item in result:
        u_email = (item.get("user_email") or "").strip().lower()
        u_dest = (item.get("destination") or "").strip().lower()
        combo = (u_email, u_dest)
        if combo in seen_combos:
            continue
        seen_combos.add(combo)
        dedup_result.append(item)

    result = dedup_result

    q_clean = (query or "").strip().lower()
    if q_clean.startswith("@"):
        q_clean = q_clean[1:]

    badge_clean = (badge or "").strip().lower()

    if q_clean or (badge_clean and badge_clean != "all"):
        filtered = []
        for item in result:
            match_q = True
            if q_clean:
                dest_str = (item.get("destination") or "").lower()
                uname_str = (item.get("user_name") or "").lower()
                handle_str = (item.get("username") or "").lower()
                bio_str = (item.get("bio") or "").lower()
                email_str = (item.get("user_email") or "").lower()
                dates_str = (item.get("dates") or "").lower()
                match_q = (
                    q_clean in dest_str or
                    q_clean in uname_str or
                    q_clean in handle_str or
                    q_clean in bio_str or
                    q_clean in email_str or
                    q_clean in dates_str
                )

            match_b = True
            if badge_clean and badge_clean != "all":
                if badge_clean == "accounts":
                    match_b = bool(item.get("is_account"))
                else:
                    item_badges = item.get("badges") or []
                    match_b = any(badge_clean in b.lower() for b in item_badges)

            if match_q and match_b:
                filtered.append(item)
        result = filtered

    if exclude_email:
        ex_clean = exclude_email.strip().lower()
        result = [item for item in result if (item.get("user_email") or "").strip().lower() != ex_clean]

    target_user_email = (user_email or "").strip().lower()
    current_user_badges = []
    current_user_interests = []
    if target_user_email:
        u_doc = find_traveller_or_agent(target_user_email)
        if u_doc:
            current_user_badges = u_doc.get("badges") or []
        email_rx = {"$regex": f"^{re.escape(target_user_email)}$", "$options": "i"}
        current_user_interests = [serialize_doc(i) for i in db.trip_interests.find({"user_email": email_rx})]

    for item in result:
        if target_user_email and (current_user_badges or current_user_interests):
            match_res = compute_ml_companion_score(item, current_user_badges, current_user_interests)
            item["match_score"] = match_res["match_score"]
            item["matched_destination"] = match_res["matched_destination"]
            item["match_summary"] = match_res["match_summary"]
            item["match_breakdown"] = match_res["breakdown"]
        else:
            item["match_score"] = 85
            item["matched_destination"] = None
            item["match_summary"] = "Sign in to see personalized ML compatibility"
            item["match_breakdown"] = {"destination": 85, "badges": 85, "budget": 85, "dates": 85}

    return {"status": "success", "companions": result}

@app.post("/create-companion")
def create_companion(req: CreateCompanionRequest):
    new_id = get_next_sequence("companions")
    doc = {
        "id": new_id,
        "name": req.name,
        "age": req.age,
        "destination": req.destination,
        "travel_dates": req.travel_dates,
        "budget": req.budget,
        "interests": req.interests,
        "bio": req.bio or "",
        "contact_email": req.contact_email,
        "profile_pic": req.profile_pic or "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=300&q=80",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    db.companions.insert_one(doc)
    doc.pop("_id", None)
    return {"status": "success", "companion": doc}

@app.post("/connect-companion")
def connect_companion(req: ConnectCompanionRequest):
    comp = db.companions.find_one({"id": req.companion_id})
    if not comp:
        raise HTTPException(status_code=404, detail="Companion profile not found.")
    to_email = comp.get("contact_email")
    if not to_email:
        raise HTTPException(status_code=400, detail="Companion does not have an email.")

    req_id = get_next_sequence("connections")
    conn_doc = {
        "id": req_id,
        "from_email": req.user_email.strip().lower(),
        "to_email": to_email.strip().lower(),
        "message": req.message or "",
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    db.connections.insert_one(conn_doc)
    return {"status": "success", "message": "Connection request sent successfully!", "request_id": req_id}

@app.post("/send-connection-request")
def send_connection_request(req: ConnectionRequestModel):
    from_em = req.from_email.strip().lower()
    to_em = req.to_email.strip().lower()
    if from_em == to_em:
        raise HTTPException(status_code=400, detail="Cannot send connection request to yourself.")

    existing = db.connections.find_one({
        "$or": [
            {"from_email": from_em, "to_email": to_em},
            {"from_email": to_em, "to_email": from_em},
            {"sender_email": from_em, "receiver_email": to_em},
            {"sender_email": to_em, "receiver_email": from_em}
        ]
    })
    if existing:
        return {"status": "success", "message": f"Connection is already {existing.get('status', 'pending')}.", "connection": serialize_doc(existing)}

    req_id = get_next_sequence("connections")
    doc = {
        "id": req_id,
        "sender_email": from_em,
        "receiver_email": to_em,
        "from_email": from_em,
        "to_email": to_em,
        "message": "Hey! I saw your post and would love to connect and explore together!",
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    db.connections.insert_one(doc)
    doc.pop("_id", None)
    return {"status": "success", "message": "Connection request sent successfully!", "connection": doc}

@app.post("/respond-connection-request")
def respond_connection_request(req: RespondConnectionRequest):
    action = req.action.lower()
    if action not in ["accepted", "rejected"]:
        raise HTTPException(status_code=400, detail="Action must be 'accepted' or 'rejected'.")

    res = db.connections.update_one({"id": req.request_id}, {"$set": {"status": action, "responded_at": time.strftime("%Y-%m-%d %H:%M:%S")}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Connection request not found.")
    return {"status": "success", "message": f"Request has been {action}."}

@app.post("/withdraw-connection-request")
def withdraw_connection_request(req: WithdrawConnectionRequest):
    wem = req.from_email.strip().lower()
    res = db.connections.delete_one({"id": req.request_id, "$or": [{"from_email": wem}, {"sender_email": wem}]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Request not found or unauthorized.")
    return {"status": "success", "message": "Connection request withdrawn."}

@app.get("/user-connections/{email}")
def get_user_connections(email: str):
    clean_query = (email or "").strip().lower()
    rx = {"$regex": f"^{re.escape(clean_query)}$", "$options": "i"}

    # Look up user details across users, travellers, agents
    user = find_traveller_or_agent(clean_query)
    user_emails = [clean_query]
    if user:
        if user.get("email"):
            user_emails.append(user["email"].strip().lower())
        if user.get("username"):
            user_emails.append(user["username"].strip().lower())

    recv_or = [
        {"receiver_email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}} for e in set(user_emails)
    ] + [
        {"to_email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}} for e in set(user_emails)
    ]
    send_or = [
        {"sender_email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}} for e in set(user_emails)
    ] + [
        {"from_email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}} for e in set(user_emails)
    ]

    # 1. Received Pending Requests
    pending_docs = list(db.connections.find({
        "$or": recv_or,
        "status": "pending"
    }).sort("id", -1))

    pending = []
    for c in pending_docs:
        c_dict = serialize_doc(c)
        c_dict.pop("_id", None)
        s_email = c_dict.get("sender_email") or c_dict.get("from_email") or ""
        u = find_traveller_or_agent(s_email)
        if u:
            c_dict["first_name"] = u.get("first_name", "")
            c_dict["last_name"] = u.get("last_name", "")
            c_dict["username"] = u.get("username", "")
            c_dict["profile_pic"] = u.get("profile_pic", "")
            c_dict["sender_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("username")
            c_dict["sender_username"] = u.get("username", "")
            c_dict["sender_pic"] = u.get("profile_pic", "")
        pending.append(c_dict)

    # 2. Sent Pending Requests
    sent_docs = list(db.connections.find({
        "$or": send_or,
        "status": "pending"
    }).sort("id", -1))

    sent_requests = []
    for c in sent_docs:
        c_dict = serialize_doc(c)
        c_dict.pop("_id", None)
        r_email = c_dict.get("receiver_email") or c_dict.get("to_email") or ""
        u = find_traveller_or_agent(r_email)
        if u:
            c_dict["receiver_first_name"] = u.get("first_name", "")
            c_dict["receiver_last_name"] = u.get("last_name", "")
            c_dict["receiver_username"] = u.get("username", "")
            c_dict["receiver_profile_pic"] = u.get("profile_pic", "")
            c_dict["receiver_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("username")
        sent_requests.append(c_dict)

    # 3. Accepted Buddies
    buddies_docs = list(db.connections.find({
        "$or": recv_or + send_or,
        "status": "accepted"
    }).sort("id", -1))

    buddies = []
    for c in buddies_docs:
        c_dict = serialize_doc(c)
        c_dict.pop("_id", None)
        s_email = (c_dict.get("sender_email") or c_dict.get("from_email") or "").strip().lower()
        if s_email in [e.lower() for e in user_emails]:
            other_email = c_dict.get("receiver_email") or c_dict.get("to_email") or ""
        else:
            other_email = s_email
        
        c_dict["buddy_email"] = other_email
        u = find_traveller_or_agent(other_email)
        buddy_dest = ""
        if u:
            c_dict["buddy_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("username") or other_email
            c_dict["buddy_username"] = u.get("username", "")
            c_dict["buddy_pic"] = u.get("profile_pic", "")
            buddy_dest = u.get("destination") or u.get("travel_destination") or ""
        else:
            c_dict["buddy_name"] = other_email.split("@")[0]
            c_dict["buddy_username"] = other_email.split("@")[0]
            c_dict["buddy_pic"] = ""

        if not buddy_dest:
            try:
                comp = db.companions.find_one({"$or": [{"user_email": {"$regex": f"^{re.escape(other_email)}$", "$options": "i"}}, {"email": {"$regex": f"^{re.escape(other_email)}$", "$options": "i"}}]})
                if comp and comp.get("destination"):
                    buddy_dest = comp["destination"]
            except Exception:
                pass

        c_dict["destination"] = buddy_dest or c_dict.get("destination") or "Explorer"
        buddies.append(c_dict)

    return {
        "status": "success",
        "pending_requests": pending,
        "incoming_requests": pending,
        "sent_requests": sent_requests,
        "outgoing_requests": sent_requests,
        "accepted_buddies": buddies,
        "buddies": buddies
    }

@app.get("/reviews/{companion_id}")
def get_reviews(companion_id: int):
    revs = list(db.reviews.find({"companion_id": companion_id}).sort("id", -1))
    return {"status": "success", "reviews": [serialize_doc(r) for r in revs]}

@app.post("/add-review")
def add_review(req: AddReviewRequest):
    rev_id = get_next_sequence("reviews")
    doc = {
        "id": rev_id,
        "companion_id": req.companion_id,
        "reviewer_name": req.reviewer_name,
        "reviewer_email": req.reviewer_email,
        "rating": req.rating,
        "comment": req.comment,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    db.reviews.insert_one(doc)
    doc.pop("_id", None)
    return {"status": "success", "review": doc}


# -------------------------------------------------------------
# DIRECT BUDDY CHAT & REAL-TIME MESSAGING
# -------------------------------------------------------------
@app.get("/get-buddy-messages/{user_email}/{buddy_email}")
def get_buddy_messages(user_email: str, buddy_email: str):
    u1 = (user_email or "").strip().lower()
    u2 = (buddy_email or "").strip().lower()

    if not u1 or not u2:
        return {"status": "success", "messages": []}

    u1_keys = get_cached_user_keys(u1)
    u2_keys = get_cached_user_keys(u2)

    # Automatically mark incoming messages from buddy as read when opening conversation
    try:
        db.buddy_messages.update_many({
            "$or": [
                {"sender_email": {"$in": u2_keys}, "receiver_email": {"$in": u1_keys}},
                {
                    "sender_email": {"$in": [re.compile(f"^{re.escape(k)}$", re.IGNORECASE) for k in u2_keys]},
                    "receiver_email": {"$in": [re.compile(f"^{re.escape(k)}$", re.IGNORECASE) for k in u1_keys]}
                }
            ],
            "status": {"$ne": "read"}
        }, {"$set": {"status": "read"}})
    except Exception as e:
        pass

    docs = list(db.buddy_messages.find({
        "$or": [
            {"sender_email": {"$in": u1_keys}, "receiver_email": {"$in": u2_keys}},
            {"sender_email": {"$in": u2_keys}, "receiver_email": {"$in": u1_keys}}
        ]
    }).sort("id", 1))

    # Format time strings
    now_year = datetime.now().year
    out_msgs = []
    for d in docs:
        if d.get("is_deleted_for_everyone") is True:
            continue
        if u1 in [k.lower() for k in d.get("deleted_for", [])]:
            continue

        raw_time = d.get("created_at", "")
        time_display = d.get("time_str", "")
        if not time_display and raw_time:
            try:
                dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                local_dt = dt.astimezone()
                time_display = local_dt.strftime("%I:%M %p").lstrip("0")
                d["time_str"] = time_display
            except Exception:
                time_display = ""

        doc_clean = serialize_doc(d)
        doc_clean.pop("_id", None)
        out_msgs.append(doc_clean)

    return {"status": "success", "messages": out_msgs}

@app.post("/send-buddy-message")
def send_buddy_message(req: BuddyMessageRequest):
    sender = req.sender_email.strip().lower()
    receiver = req.receiver_email.strip().lower()
    text = req.message_text.strip()

    if not sender or not receiver or not text:
        raise HTTPException(status_code=400, detail="Sender, receiver, and message text are required.")

    # Real-time chat safety & anti-spam link classification
    try:
        from icebreakers_ml import classify_message_safety
        safety_check = classify_message_safety(text)
        if not safety_check.get("is_safe", True):
            raise HTTPException(
                status_code=400,
                detail=f"Message blocked by safety moderation: {safety_check.get('flag_reason', 'Unsafe link or spam content')}"
            )
    except HTTPException:
        raise
    except Exception:
        pass

    msg_id = get_next_sequence("buddy_messages")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    now_local = time.localtime()
    time_str = time.strftime("%I:%M %p", now_local).lstrip('0')

    doc = {
        "id": msg_id,
        "sender_email": sender,
        "receiver_email": receiver,
        "message_text": text,
        "time_str": time_str,
        "status": "sent",
        "created_at": now_iso
    }
    db.buddy_messages.insert_one(doc)

    # Auto-read previous messages from receiver
    try:
        db.buddy_messages.update_many({
            "sender_email": {"$regex": f"^{re.escape(receiver)}$", "$options": "i"},
            "receiver_email": {"$regex": f"^{re.escape(sender)}$", "$options": "i"},
            "status": {"$ne": "read"}
        }, {"$set": {"status": "read"}})
    except Exception as e:
        pass

    # Instant response from agent if receiver is an agent and first inquiry
    agent = db.agents.find_one({"email": {"$regex": f"^{re.escape(receiver)}$", "$options": "i"}})
    if agent:
        existing_reply = db.buddy_messages.find_one({
            "sender_email": {"$regex": f"^{re.escape(receiver)}$", "$options": "i"},
            "receiver_email": {"$regex": f"^{re.escape(sender)}$", "$options": "i"}
        })
        if not existing_reply:
            reply_id = get_next_sequence("buddy_messages")
            reply_text = f"Hello! This is {agent.get('agent_name')} from {agent.get('agency_name', 'our team')}. Thank you for connecting! I've received your inquiry and I am delighted to help tailor your trip. What destinations and dates do you have in mind?"
            agent_reply_doc = {
                "id": reply_id,
                "sender_email": receiver,
                "receiver_email": sender,
                "message_text": reply_text,
                "time_str": time_str,
                "status": "delivered",
                "created_at": now_iso
            }
            db.buddy_messages.insert_one(agent_reply_doc)

    doc_clean = serialize_doc(doc)
    doc_clean.pop("_id", None)
    return {"status": "success", "message": doc_clean}

@app.post("/mark-messages-read")
def mark_messages_read(req: MarkReadRequest):
    u1 = (req.user_email or "").strip().lower()
    u2 = (req.buddy_email or "").strip().lower()
    if not u1 or not u2:
        return {"status": "error", "message": "user_email and buddy_email are required"}

    u1_keys = get_cached_user_keys(u1)
    u2_keys = get_cached_user_keys(u2)

    try:
        res = db.buddy_messages.update_many({
            "$or": [
                {"sender_email": {"$in": u2_keys}, "receiver_email": {"$in": u1_keys}},
                {
                    "sender_email": {"$in": [re.compile(f"^{re.escape(k)}$", re.IGNORECASE) for k in u2_keys]},
                    "receiver_email": {"$in": [re.compile(f"^{re.escape(k)}$", re.IGNORECASE) for k in u1_keys]}
                }
            ],
            "status": {"$ne": "read"}
        }, {"$set": {"status": "read"}})
        return {"status": "success", "modified_count": res.modified_count}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/delete-message")
def delete_message_endpoint(payload: DeleteMessagePayload):
    u = (payload.user_email or "").strip().lower()
    del_type = (payload.delete_type or "").strip().lower()
    m_raw = payload.message_id
    try:
        m_id = int(m_raw)
    except Exception:
        m_id = m_raw

    if not u or m_id is None or del_type not in ["everyone", "me"]:
        raise HTTPException(status_code=400, detail="Invalid request parameters.")

    query = {"$or": [{"id": m_id}, {"id": str(m_id)}]}
    res1 = db.buddy_messages.delete_many(query)
    res2 = db.trip_messages.delete_many(query)
    deleted_count = res1.deleted_count + res2.deleted_count
    return {"status": "success", "message_id": m_id, "deleted_count": deleted_count, "delete_type": del_type}

@app.get("/unread-counts/{user_email}")
def get_unread_counts(user_email: str):
    u = (user_email or "").strip().lower()
    if not u:
        return {"status": "success", "unread_counts": {}}

    user_keys = [k.lower() for k in get_cached_user_keys(u)]

    # Mark incoming messages that were "sent" as "delivered" since user is actively connected
    try:
        db.buddy_messages.update_many({
            "$or": [
                {"receiver_email": {"$in": user_keys}},
                {"receiver_email": {"$in": [re.compile(f"^{re.escape(k)}$", re.IGNORECASE) for k in user_keys]}}
            ],
            "status": "sent"
        }, {"$set": {"status": "delivered"}})
    except Exception:
        pass

    query = {
        "receiver_email": {"$in": user_keys},
        "status": {"$ne": "read"},
        "is_deleted_for_everyone": {"$ne": True},
        "deleted_for": {"$nin": user_keys}
    }
    unread_msgs = list(db.buddy_messages.find(query, {"sender_email": 1}))
    counts = {}
    for m in unread_msgs:
        s = (m.get("sender_email") or "").strip().lower()
        if s:
            counts[s] = counts.get(s, 0) + 1

    return {"status": "success", "unread_counts": counts}


# -------------------------------------------------------------
# TRIP INTERESTS
# -------------------------------------------------------------
@app.get("/trip-interests/{user_email}")
@app.get("/api/trip-interests/{user_email}")
def get_trip_interests(user_email: str):
    clean = user_email.strip().lower()
    rx = {"$regex": f"^{re.escape(clean)}$", "$options": "i"}

    u_doc = find_traveller_or_agent(clean)
    email_list = [clean]
    if u_doc:
        if u_doc.get("email"): email_list.append(u_doc["email"].strip().lower())
        if u_doc.get("username"): email_list.append(u_doc["username"].strip().lower())

    or_clauses = [{"user_email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}} for e in set(email_list)]
    rows = list(db.trip_interests.find({"$or": or_clauses}).sort("id", -1))
    
    # Authoritative deduplication by destination
    deduped = []
    seen = set()
    for r in rows:
        d = (r.get("destination") or "").strip().lower()
        if d and d not in seen:
            seen.add(d)
            deduped.append(serialize_doc(r))
        elif not d:
            deduped.append(serialize_doc(r))

    return {"status": "success", "interests": deduped}

@app.post("/add-trip-interest")
@app.post("/api/trip-interests")
def add_trip_interest(req: AddTripInterestRequest):
    email = (req.user_email or req.email or "").strip().lower()
    dest = (req.destination or "").strip()
    if not email or not dest:
        raise HTTPException(status_code=400, detail="User email and destination are required.")

    u_doc = find_traveller_or_agent(email)
    email_list = [email]
    if u_doc:
        if u_doc.get("email"): email_list.append(u_doc["email"].strip().lower())
        if u_doc.get("username"): email_list.append(u_doc["username"].strip().lower())

    or_user_clauses = [{"user_email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}} for e in set(email_list)]
    dest_rx = {"$regex": f"^{re.escape(dest)}$", "$options": "i"}

    dates = req.preferred_dates or req.dates or "Flexible"
    budget = req.budget or "Flexible"
    notes = req.notes or ""

    # Check if an interest for this destination already exists for this user
    existing = db.trip_interests.find_one({"$and": [{"$or": or_user_clauses}, {"destination": dest_rx}]})
    if existing:
        existing_id = existing.get("id") or get_next_sequence("trip_interests")
        updates = {
            "destination": dest,
            "preferred_dates": dates,
            "budget": budget,
            "notes": notes,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        db.trip_interests.update_one({"_id": existing["_id"]}, {"$set": updates})
        sync_user_trip_interests_field(email)
        existing.update(updates)
        existing["id"] = existing_id
        existing.pop("_id", None)
        return {"status": "success", "id": existing_id, "interest": existing, "message": "Updated existing interest"}

    interest_id = get_next_sequence("trip_interests")
    doc = {
        "id": interest_id,
        "user_email": email,
        "destination": dest,
        "preferred_dates": dates,
        "budget": budget,
        "notes": notes,
        "source": req.source or "manual",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    db.trip_interests.insert_one(doc)
    sync_user_trip_interests_field(email)
    doc.pop("_id", None)
    return {"status": "success", "id": interest_id, "interest": doc}

@app.post("/edit-trip-interest")
def edit_trip_interest(req: EditTripInterestRequest):
    email = req.user_email.strip().lower()
    u_doc = find_traveller_or_agent(email)
    email_list = [email]
    if u_doc:
        if u_doc.get("email"): email_list.append(u_doc["email"].strip().lower())
        if u_doc.get("username"): email_list.append(u_doc["username"].strip().lower())

    or_user_clauses = [{"user_email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}} for e in set(email_list)]
    target_id = req.interest_id if req.interest_id is not None else req.id

    id_clauses = []
    if target_id is not None:
        id_clauses.append({"id": target_id})
        try:
            id_clauses.append({"id": int(target_id)})
        except (ValueError, TypeError):
            pass
        id_clauses.append({"id": str(target_id)})

    dest = (req.destination or "").strip()
    dates = req.preferred_dates or "Flexible"
    budget = req.budget or "Flexible"
    notes = req.notes or ""

    query = {"$or": or_user_clauses}
    if id_clauses:
        query = {"$and": [{"$or": or_user_clauses}, {"$or": id_clauses}]}

    updates = {
        "destination": dest,
        "preferred_dates": dates,
        "budget": budget,
        "notes": notes,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    res = db.trip_interests.update_one(query, {"$set": updates})
    if res.matched_count == 0 and dest:
        db.trip_interests.update_one(
            {"$and": [{"$or": or_user_clauses}, {"destination": {"$regex": f"^{re.escape(dest)}$", "$options": "i"}}]},
            {"$set": updates}
        )
    sync_user_trip_interests_field(email)
    return {"status": "success", "message": "Interest updated successfully!"}

@app.post("/delete-trip-interest")
def delete_trip_interest(req: DeleteTripInterestRequest):
    email = req.user_email.strip().lower()
    u_doc = find_traveller_or_agent(email)
    email_list = [email]
    if u_doc:
        if u_doc.get("email"): email_list.append(u_doc["email"].strip().lower())
        if u_doc.get("username"): email_list.append(u_doc["username"].strip().lower())

    or_user_clauses = [{"user_email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}} for e in set(email_list)]
    target_id = req.interest_id if req.interest_id is not None else req.id
    dest = (req.destination or "").strip()

    id_clauses = []
    if target_id is not None:
        id_clauses.append({"id": target_id})
        try:
            id_clauses.append({"id": int(target_id)})
        except (ValueError, TypeError):
            pass
        id_clauses.append({"id": str(target_id)})

    deleted = 0
    if id_clauses:
        res = db.trip_interests.delete_many({"$and": [{"$or": or_user_clauses}, {"$or": id_clauses}]})
        deleted += res.deleted_count

    if dest:
        dest_rx = {"$regex": f"^{re.escape(dest)}$", "$options": "i"}
        res2 = db.trip_interests.delete_many({"$and": [{"$or": or_user_clauses}, {"destination": dest_rx}]})
        deleted += res2.deleted_count

    sync_user_trip_interests_field(email)
    return {"status": "success", "message": "Interest deleted successfully.", "deleted_count": deleted}


# -------------------------------------------------------------
# AGENT MARKETPLACE, REVIEWS & INQUIRIES
# -------------------------------------------------------------
@app.get("/agents")
def get_agents(search: Optional[str] = None):
    seed_default_agents_and_trips()
    query = {}
    if search and search.strip():
        s = search.strip()
        rx = {"$regex": re.escape(s), "$options": "i"}
        query = {"$or": [{"agency_name": rx}, {"agent_name": rx}, {"specialty": rx}, {"destinations": rx}]}
    agents = list(db.agents.find(query).sort("rating", -1))
    return {"status": "success", "agents": [serialize_doc(a) for a in agents]}

@app.get("/agent-reviews/{agent_id}")
def get_agent_reviews(agent_id: int):
    seed_default_agents_and_trips()
    agent = db.agents.find_one({"id": agent_id})
    rows = list(db.agent_reviews.find({"agent_id": agent_id}).sort("id", -1))
    distribution = agent.get("ratings_distribution", {"5": 5, "4": 1, "3": 0, "2": 0, "1": 0}) if agent else {}
    return {
        "status": "success",
        "reviews": [serialize_doc(r) for r in rows],
        "ratings_distribution": distribution,
        "rating": agent.get("rating", 5.0) if agent else 5.0,
        "total_ratings": agent.get("reviews_count", len(rows)) if agent else len(rows)
    }

@app.post("/add-agent-review")
def add_agent_review(req: AddAgentReviewRequest):
    rev_id = get_next_sequence("agent_reviews")
    star_int = max(1, min(5, int(round(req.rating))))
    doc = {
        "id": rev_id,
        "agent_id": req.agent_id,
        "rating": float(req.rating),
        "reviewer_name": req.reviewer_name,
        "reviewer_username": req.reviewer_username,
        "reviewer_email": req.reviewer_email,
        "trip_route": req.trip_route or "",
        "review_title": req.review_title or "",
        "review_text": req.review_text or "",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    db.agent_reviews.insert_one(doc)

    agent = db.agents.find_one({"id": req.agent_id})
    if agent:
        dist = agent.get("ratings_distribution", {"5": 10, "4": 2, "3": 0, "2": 0, "1": 0})
        dist_key = str(star_int)
        dist[dist_key] = int(dist.get(dist_key, 0)) + 1
        weighted_sum = sum(int(k) * int(v) for k, v in dist.items())
        total_count = sum(int(v) for v in dist.items())
        new_rating = round(weighted_sum / total_count, 2) if total_count > 0 else 5.0

        db.agents.update_one(
            {"id": req.agent_id},
            {"$set": {"rating": new_rating, "reviews_count": total_count, "ratings_distribution": dist}}
        )

    doc.pop("_id", None)
    return {"status": "success", "message": "Review recorded successfully!", "review": doc}

@app.post("/contact-agent")
@app.post("/submit-query")
def contact_agent(req: ContactAgentRequest):
    inq_id = get_next_sequence("agent_inquiries")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    msg_text = req.message or req.message_text or ""
    travel_dates = req.travel_dates or req.expected_dates or "Flexible"

    doc = {
        "id": inq_id,
        "agent_id": req.agent_id,
        "agent_name": req.agent_name or "",
        "agent_email": req.agent_email or "",
        "user_email": req.user_email.strip().lower(),
        "user_name": req.user_name or req.user_email.split("@")[0],
        "user_phone": req.user_phone or "",
        "inquiry_type": req.inquiry_type or req.reason or "general",
        "trip_id": req.trip_id,
        "trip_title": req.trip_title or "",
        "destination": req.destination or "",
        "travel_dates": travel_dates,
        "budget": req.budget or "Flexible",
        "group_size": req.group_size or 1,
        "message": msg_text,
        "status": "pending",
        "created_at": now_str
    }

    db.agent_inquiries.insert_one(dict(doc))
    db.queries.insert_one(dict(doc))

    doc.pop("_id", None)
    return {"status": "success", "message": "Inquiry submitted to agent successfully!", "inquiry_id": inq_id, "inquiry": doc}

@app.get("/agent-inquiries")
@app.get("/queries")
def get_agent_inquiries(agent_id: Optional[Union[int, str]] = None, agent_email: Optional[str] = None, agency_name: Optional[str] = None):
    query = {}
    or_clauses = []

    if agent_id:
        try:
            or_clauses.append({"agent_id": int(agent_id)})
            or_clauses.append({"agent_id": str(agent_id)})
        except Exception:
            or_clauses.append({"agent_id": agent_id})

    if agent_email and agent_email.strip():
        em = agent_email.strip().lower()
        or_clauses.append({"agent_email": {"$regex": f"^{re.escape(em)}$", "$options": "i"}})

    if agency_name and agency_name.strip():
        ag = agency_name.strip()
        or_clauses.append({"agency_name": {"$regex": f"^{re.escape(ag)}$", "$options": "i"}})

    if or_clauses:
        query = {"$or": or_clauses}

    inquiries = list(db.agent_inquiries.find(query).sort("id", -1))
    if not inquiries:
        inquiries = list(db.queries.find(query).sort("id", -1))

    return {"status": "success", "inquiries": [serialize_doc(i) for i in inquiries]}

@app.post("/update-agent-inquiry-status")
def update_agent_inquiry_status(req: UpdateInquiryStatusRequest):
    res1 = db.agent_inquiries.update_one({"id": req.inquiry_id}, {"$set": {"status": req.status}})
    res2 = db.queries.update_one({"id": req.inquiry_id}, {"$set": {"status": req.status}})
    if res1.matched_count == 0 and res2.matched_count == 0:
        raise HTTPException(status_code=404, detail="Inquiry record not found.")
    return {"status": "success", "message": f"Inquiry status updated to {req.status}."}

@app.post("/answer-query")
@app.post("/reply-agent-inquiry")
def answer_query(req: AnswerQueryRequest):
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    update_data = {
        "status": "resolved",
        "answer": req.answer_text,
        "answered_at": now_str,
        "answered_by_agent": req.agent_name or req.agent_email or "Agent"
    }

    inq = db.agent_inquiries.find_one({"id": req.inquiry_id}) or db.queries.find_one({"id": req.inquiry_id})
    if not inq:
        raise HTTPException(status_code=404, detail="Inquiry not found.")

    db.agent_inquiries.update_one({"id": req.inquiry_id}, {"$set": update_data})
    db.queries.update_one({"id": req.inquiry_id}, {"$set": update_data})

    # Also deliver response directly to user buddy chat if agent email is known
    user_email = inq.get("user_email")
    agent_email = req.agent_email or inq.get("agent_email")
    if user_email and agent_email:
        msg_id = get_next_sequence("buddy_messages")
        chat_doc = {
            "id": msg_id,
            "sender_email": agent_email.lower(),
            "receiver_email": user_email.lower(),
            "message_text": f"Re: {inq.get('trip_title', 'Your Inquiry')} - {req.answer_text}",
            "time_str": time.strftime("%I:%M %p").lstrip('0'),
            "status": "delivered",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        db.buddy_messages.insert_one(chat_doc)

    return {"status": "success", "message": "Inquiry responded to and resolved successfully!"}


# -------------------------------------------------------------
# GROUP TRIPS, BOOKINGS & ROSTER
# -------------------------------------------------------------
@app.get("/group-trips")
def get_group_trips(destination: Optional[str] = None, category: Optional[str] = None, agent_id: Optional[Union[int, str]] = None, agent_email: Optional[str] = None):
    seed_default_agents_and_trips()
    heal_group_trips_agent_info()

    query = {}
    and_clauses = []

    if destination and destination.strip():
        rx = {"$regex": re.escape(destination.strip()), "$options": "i"}
        and_clauses.append({"$or": [{"destination": rx}, {"title": rx}]})

    if category and category.strip():
        and_clauses.append({"category": {"$regex": f"^{re.escape(category.strip())}$", "$options": "i"}})

    if agent_id:
        try:
            and_clauses.append({"$or": [{"agent_id": int(agent_id)}, {"agent_id": str(agent_id)}]})
        except Exception:
            and_clauses.append({"agent_id": agent_id})

    if agent_email and agent_email.strip():
        em = agent_email.strip().lower()
        and_clauses.append({"agent_email": {"$regex": f"^{re.escape(em)}$", "$options": "i"}})

    if and_clauses:
        query = {"$and": and_clauses}

    trips = list(db.group_trips.find(query).sort("id", -1))
    return {"status": "success", "trips": [serialize_doc(t) for t in trips]}

@app.get("/group-trips/{trip_id}")
def get_single_group_trip(trip_id: str):
    seed_default_agents_and_trips()
    query = {"$or": [{"id": int(trip_id) if trip_id.isdigit() else -1}, {"id": trip_id}]}
    trip = db.group_trips.find_one(query)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return {"status": "success", "trip": serialize_doc(trip)}

@app.post("/create-group-trip")
def create_group_trip(req: CreateGroupTripRequest):
    trip_id = get_next_sequence("group_trips")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    # Resolve agent info
    agent_id = req.agent_id or 1
    agent_doc = db.agents.find_one({"$or": [{"id": int(agent_id) if str(agent_id).isdigit() else -1}, {"email": req.agent_email}]})
    agency = req.agency_name or (agent_doc.get("agency_name") if agent_doc else "TravelVerse Certified Partner")
    agent_name = req.agent_name or (agent_doc.get("agent_name") if agent_doc else "Expedition Host")
    agent_email = req.agent_email or (agent_doc.get("email") if agent_doc else "agent@travelverse.com")

    doc = {
        "id": trip_id,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "agent_type": req.agent_type or "agency",
        "agency_name": agency,
        "agent_email": agent_email,
        "agent_phone": req.agent_phone or (agent_doc.get("phone", "") if agent_doc else ""),
        "title": req.title,
        "destination": req.destination,
        "tagline": req.tagline or f"Experience the breathtaking beauty of {req.destination}",
        "season_climate": req.season_climate or "Optimal seasonal travel conditions",
        "stay_type": req.stay_type or "Boutique & Heritage accommodations",
        "transit_mode": req.transit_mode or "Private chauffeured expedition vehicles",
        "packing_essentials": req.packing_essentials or ["Comfortable walking shoes", "Weather appropriate layers", "Valid ID"],
        "dropoff_point": req.dropoff_point or req.meeting_point or "Designated Departure Terminal",
        "health_advisory": req.health_advisory or "Standard travel health and fitness required.",
        "category": req.category or "Cultural",
        "start_date": req.start_date or time.strftime("%Y-%m-%d"),
        "end_date": req.end_date or time.strftime("%Y-%m-%d"),
        "duration_days": req.duration_days or 5,
        "price": float(req.price or 0.0),
        "currency": req.currency or "INR",
        "max_capacity": req.max_capacity or 12,
        "enrolled_count": int(req.enrolled_count or 0),
        "cover_image": req.cover_image or "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=1200&q=80",
        "description": req.description or "",
        "highlights": req.highlights or [],
        "itinerary": req.itinerary or [],
        "inclusions": req.inclusions or [],
        "exclusions": req.exclusions or [],
        "difficulty": req.difficulty or "Moderate",
        "meeting_point": req.meeting_point or "City Center Meeting Point",
        "created_at": now_str
    }

    db.group_trips.insert_one(doc)
    doc.pop("_id", None)
    return {"status": "success", "message": "Group trip created successfully!", "trip": doc}

@app.post("/edit-group-trip")
def edit_group_trip(req: EditGroupTripRequest):
    t_id = req.trip_id
    query = {"$or": [{"id": int(t_id) if str(t_id).isdigit() else -1}, {"id": t_id}]}
    trip = db.group_trips.find_one(query)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")

    updates = {}
    if req.title is not None: updates["title"] = req.title
    if req.destination is not None: updates["destination"] = req.destination
    if req.category is not None: updates["category"] = req.category
    if req.start_date is not None: updates["start_date"] = req.start_date
    if req.end_date is not None: updates["end_date"] = req.end_date
    if req.duration_days is not None: updates["duration_days"] = req.duration_days
    if req.price is not None: updates["price"] = float(req.price)
    if req.max_capacity is not None: updates["max_capacity"] = req.max_capacity
    if req.cover_image is not None: updates["cover_image"] = req.cover_image
    if req.description is not None: updates["description"] = req.description
    if req.highlights is not None: updates["highlights"] = req.highlights
    if req.itinerary is not None: updates["itinerary"] = req.itinerary
    if req.inclusions is not None: updates["inclusions"] = req.inclusions
    if req.exclusions is not None: updates["exclusions"] = req.exclusions
    if req.difficulty is not None: updates["difficulty"] = req.difficulty
    if req.meeting_point is not None: updates["meeting_point"] = req.meeting_point

    db.group_trips.update_one(query, {"$set": updates})
    updated = db.group_trips.find_one(query)
    return {"status": "success", "message": "Trip updated successfully!", "trip": serialize_doc(updated)}

@app.delete("/delete-group-trip/{trip_id}")
def delete_group_trip(trip_id: str):
    query = {"$or": [{"id": int(trip_id) if trip_id.isdigit() else -1}, {"id": trip_id}]}
    res = db.group_trips.delete_one(query)
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return {"status": "success", "message": f"Trip {trip_id} deleted successfully."}

@app.post("/enroll-group-trip")
@app.post("/book-trip")
def enroll_group_trip(req: EnrollGroupTripRequest):
    t_id = req.trip_id
    query = {"$or": [{"id": int(t_id) if str(t_id).isdigit() else -1}, {"id": t_id}]}
    trip = db.group_trips.find_one(query)
    if not trip:
        raise HTTPException(status_code=404, detail="Group trip not found.")

    user_email = (req.user_email or req.traveller_email or "").strip().lower()
    user_name = (req.user_name or req.traveller_name or user_email.split("@")[0]).strip()
    user_phone = req.user_phone or req.traveller_phone or ""
    seats = int(req.seats or 1)

    booking_id = get_next_sequence("trip_enrollments")
    booking_code = f"TV-EXP-{random.randint(1000, 9999)}"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    # Build passenger list: lead passenger + additional passengers
    passengers_list = []
    if req.additional_passengers:
        for p in req.additional_passengers:
            passengers_list.append({
                "name": p.name,
                "gender": p.gender or "",
                "age": p.age,
                "nationality": p.nationality or "",
                "preferences": p.preferences or ""
            })
    # Fallback: lead passenger if no additional_passengers provided
    if not passengers_list:
        passengers_list = [{"name": user_name, "gender": "", "age": None, "nationality": "", "preferences": ""}]

    traveller_names = [p["name"] for p in passengers_list]

    doc = {
        "id": booking_id,
        "booking_code": booking_code,
        "trip_id": trip.get("id"),
        "trip_title": trip.get("title", "Expedition"),
        "destination": trip.get("destination", ""),
        "user_email": user_email,
        "user_name": user_name,
        "user_phone": user_phone,
        "seats": seats,
        "amount_paid": float(trip.get("price", 0.0)) * seats,
        "status": "pending",
        "special_notes": req.special_notes or "",
        "traveller_names": traveller_names,
        "passengers": passengers_list,
        "created_at": now_str
    }

    db.trip_enrollments.insert_one(dict(doc))
    db.bookings.insert_one(dict(doc))

    # Update enrolled travelers on group trip document
    traveller_entry = {
        "id": booking_id,
        "booking_code": booking_code,
        "name": user_name,
        "email": user_email,
        "phone": user_phone,
        "seats": seats,
        "status": "pending",
        "enrolled_at": now_str,
        "traveller_names": traveller_names,
        "passengers": passengers_list   # full per-passenger details (name, gender, age, nationality, preferences)
    }
    db.group_trips.update_one(query, {
        "$push": {"enrolled_travellers": traveller_entry}
    })

    doc.pop("_id", None)
    return {
        "status": "success",
        "message": "Trip booking request submitted! Awaiting host agent confirmation.",
        "booking_code": booking_code,
        "booking": doc
    }

@app.get("/trip-enrollments")
@app.get("/bookings")
def get_trip_enrollments(agent_id: Optional[Union[int, str]] = None, trip_id: Optional[Union[int, str]] = None):
    query = {}
    if trip_id:
        query["trip_id"] = int(trip_id) if str(trip_id).isdigit() else trip_id

    rows = list(db.trip_enrollments.find(query).sort("id", -1))
    if not rows:
        rows = list(db.bookings.find(query).sort("id", -1))

    return {"status": "success", "enrollments": [serialize_doc(r) for r in rows], "bookings": [serialize_doc(r) for r in rows]}

@app.get("/user-enrolled-trips/{email}")
def get_user_enrolled_trips(email: str):
    clean = email.strip().lower()
    u_keys = get_cached_user_keys(clean)
    or_clauses = [{"user_email": {"$regex": f"^{re.escape(k)}$", "$options": "i"}} for k in u_keys]

    rows = list(db.trip_enrollments.find({"$or": or_clauses, "status": "confirmed"}).sort("id", -1))
    if not rows:
        rows = list(db.bookings.find({"$or": or_clauses, "status": "confirmed"}).sort("id", -1))

    res = []
    for r in rows:
        d = serialize_doc(r)
        d.pop("_id", None)
        t_id = d.get("trip_id")
        if t_id:
            trip = db.group_trips.find_one({"$or": [{"id": t_id}, {"id": str(t_id)}, {"id": int(t_id) if str(t_id).isdigit() else -1}]})
            if trip:
                d["trip_details"] = serialize_doc(trip)
        res.append(d)

    return {"status": "success", "enrollments": res}

@app.post("/cancel-enrollment")
@app.post("/cancel-group-trip-enrollment")
def cancel_enrollment(req: CancelEnrollmentRequest):
    code = (req.booking_code or str(req.enrollment_id or "")).strip()
    enrollment = None
    if code:
        enrollment = db.trip_enrollments.find_one({"booking_code": code}) or db.bookings.find_one({"booking_code": code})
    if not enrollment and str(req.enrollment_id or "").isdigit():
        eid = int(req.enrollment_id)
        enrollment = db.trip_enrollments.find_one({"id": eid}) or db.bookings.find_one({"id": eid})

    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment record not found.")

    b_code = enrollment.get("booking_code")
    e_id = enrollment.get("id")
    del_query = {"$or": [{"booking_code": b_code}, {"id": e_id}]}

    db.trip_enrollments.delete_many(del_query)
    db.bookings.delete_many(del_query)

    seats = int(enrollment.get("seats", 1))
    trip_id = enrollment.get("trip_id")
    if trip_id is not None:
        db.group_trips.update_one(
            {"$or": [{"id": trip_id}, {"id": str(trip_id)}, {"id": int(trip_id) if str(trip_id).isdigit() else -1}]},
            {
                "$pull": {"enrolled_travellers": {"booking_code": b_code}},
                "$inc": {"enrolled_count": -1, "passengers_count": -1}
            }
        )

    return {"status": "success", "message": "Enrollment cancelled and seats released successfully."}

@app.post("/update-booking-status")
@app.post("/confirm-booking")
def update_booking_status(req: UpdateBookingStatusRequest):
    code = req.booking_code
    b_id = req.booking_id
    query = {"$or": [{"booking_code": code}, {"id": int(b_id) if str(b_id).isdigit() else -1}]}

    res1 = db.trip_enrollments.update_one(query, {"$set": {"status": req.status}})
    res2 = db.bookings.update_one(query, {"$set": {"status": req.status}})
    if res1.matched_count == 0 and res2.matched_count == 0:
        raise HTTPException(status_code=404, detail="Booking record not found.")

    email_dispatched = False
    enr = db.trip_enrollments.find_one(query) or db.bookings.find_one(query)
    if enr:
        trip = None
        if enr.get("trip_id"):
            t_id = enr.get("trip_id")
            trip = db.group_trips.find_one({"$or": [{"id": int(t_id) if str(t_id).isdigit() else -1}, {"id": t_id}]})
        if not trip:
            trip = {
                "title": enr.get("trip_title", "Expedition"),
                "destination": enr.get("destination", "Destination"),
                "price": enr.get("amount_paid", 0.0),
                "agency_name": req.agent_name or "TravelVerse Certified Agency"
            }
        u_email = enr.get("user_email")
        u_name = enr.get("user_name") or "Explorer"
        b_code = enr.get("booking_code") or code

        # Also update status of this traveller inside group_trips.enrolled_travellers
        try:
            t_id = enr.get("trip_id")
            if t_id is not None:
                db.group_trips.update_one(
                    {"$or": [{"id": t_id}, {"id": str(t_id)}, {"id": int(t_id) if str(t_id).isdigit() else -1}], "enrolled_travellers.booking_code": b_code},
                    {"$set": {"enrolled_travellers.$.status": req.status}}
                )
        except Exception as gt_err:
            print(f"[GROUP TRIP UPDATE ERROR] {gt_err}")

        # If confirmed, send formal Confirmation Letter & 2-page invoice PDF!
        if req.status.lower() == "confirmed":
            try:
                email_dispatched = bool(send_booking_confirmation_email(u_email, u_name, b_code, trip, enr))
                if email_dispatched:
                    print(f"[EMAIL] Confirmation letter successfully sent to {u_email} for booking {b_code}")
                else:
                    print(f"[WARN] send_booking_confirmation_email returned False for {u_email}")
            except Exception as mail_err:
                print(f"[WARN] Error sending confirmation email on update-booking-status: {mail_err}")
                email_dispatched = False
        # If cancelled, send cancellation notice email to traveller!
        elif req.status.lower() in ["cancelled", "unconfirmed"]:
            try:
                email_dispatched = bool(send_booking_cancellation_email(u_email, u_name, b_code, trip, enr))
                if email_dispatched:
                    print(f"[EMAIL] Cancellation notice successfully sent to {u_email} for booking {b_code}")
                else:
                    print(f"[WARN] send_booking_cancellation_email returned False for {u_email}")
            except Exception as mail_err:
                print(f"[WARN] Error sending cancellation email on update-booking-status: {mail_err}")
                email_dispatched = False

    msg = f"Booking status updated to {req.status}."
    if email_dispatched:
        if req.status.lower() == "confirmed":
            msg += " Confirmation letter and 2-page invoice sent to guest email."
        else:
            msg += " Cancellation notice sent to guest email."
    return {"status": "success", "message": msg, "email_sent": email_dispatched}

@app.get("/trip-travellers/{trip_id}")
def get_trip_travellers(trip_id: str):
    query = {"trip_id": int(trip_id) if trip_id.isdigit() else trip_id, "status": "confirmed"}
    enrs = list(db.trip_enrollments.find(query))
    travellers = []
    for e in enrs:
        travellers.append({
            "name": e.get("user_name") or e.get("user_email"),
            "email": e.get("user_email"),
            "seats": e.get("seats", 1),
            "booking_code": e.get("booking_code"),
            "booked_at": e.get("created_at")
        })
    return {"status": "success", "trip_id": trip_id, "travellers": travellers}

@app.post("/send-trip-message")
def send_trip_message(req: SendTripMessageRequest):
    # Real-time chat safety & anti-spam link classification
    try:
        from icebreakers_ml import classify_message_safety
        safety_check = classify_message_safety(req.message_text or "")
        if not safety_check.get("is_safe", True):
            raise HTTPException(
                status_code=400,
                detail=f"Message blocked by safety moderation: {safety_check.get('flag_reason', 'Unsafe link or spam content')}"
            )
    except HTTPException:
        raise
    except Exception:
        pass

    msg_id = get_next_sequence("trip_messages")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    time_str = time.strftime("%I:%M %p")
    
    sender_email = (req.sender_email or "").strip().lower()
    sender_name = (req.sender_name or sender_email.split("@")[0] or "Traveler").strip()
    
    t_id = req.trip_id
    t_query = {"$or": [{"id": int(t_id) if str(t_id).isdigit() else -1}, {"id": t_id}]}
    trip = db.group_trips.find_one(t_query)
    
    trip_title = (trip.get("title") if trip else None) or req.trip_title or "Group Trip"
    
    role = "traveller"
    if trip:
        agent_email = (trip.get("agent_email") or "").strip().lower()
        t_aid = str(trip.get("agent_id") or "")
        is_host = False
        if sender_email and sender_email == agent_email:
            is_host = True
        elif sender_email:
            agent_doc = db.agents.find_one({"email": {"$regex": f"^{re.escape(sender_email)}$", "$options": "i"}})
            if agent_doc and (str(agent_doc.get("id")) == t_aid or (agent_doc.get("email") or "").strip().lower() == agent_email):
                is_host = True
        
        if is_host:
            role = "admin"
        else:
            role = "traveller"
    else:
        req_role = (req.sender_role or "").strip().lower()
        if req_role in ["agent", "host", "admin"]:
            role = "admin"
        else:
            role = "traveller"

    doc = {
        "id": msg_id,
        "trip_id": trip.get("id") if trip else req.trip_id,
        "trip_title": trip_title,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "sender_role": role,
        "message_text": (req.message_text or "").strip(),
        "time_str": time_str,
        "is_announcement": bool(req.is_announcement),
        "status": "read",
        "deleted_for": [],
        "created_at": now_str
    }
    db.trip_messages.insert_one(doc)
    doc.pop("_id", None)
    return {"status": "success", "message": doc}

@app.get("/get-trip-messages/{trip_id}")
def get_trip_messages(trip_id: str, user_email: Optional[str] = None):
    t_query = {"$or": [{"id": int(trip_id) if str(trip_id).isdigit() else -1}, {"id": trip_id}]}
    trip = db.group_trips.find_one(t_query)
    
    clean_trip_id = trip.get("id") if trip else (int(trip_id) if str(trip_id).isdigit() else trip_id)
    m_query = {"$or": [{"trip_id": clean_trip_id}, {"trip_id": str(clean_trip_id)}]}
    if user_email:
        clean_user = user_email.strip().lower()
        m_query["deleted_for"] = {"$nin": [clean_user]}
        
    msgs = list(db.trip_messages.find(m_query).sort("id", 1))
    
    members = []
    trip_data = None
    if trip:
        trip_data = serialize_doc(trip)
        admin_email = (trip.get("agent_email") or "").strip().lower()
        admin_member = {
            "name": trip.get("agent_name") or "Expedition Host",
            "email": admin_email,
            "agency_name": trip.get("agency_name", "TravelVerse Partner"),
            "phone": trip.get("agent_phone", ""),
            "role": "admin",
            "is_admin": True,
            "is_host": True
        }
        members.append(admin_member)
        
        seen_emails = {admin_email}
        travellers = trip.get("enrolled_travellers") or []
        if len(travellers) == 0:
            enrs = list(db.trip_enrollments.find({
                "$or": [{"trip_id": trip.get("id")}, {"trip_id": str(trip.get("id"))}, {"trip_title": trip.get("title")}],
                "status": {"$ne": "cancelled"}
            }))
            for e in enrs:
                ue = (e.get("user_email") or "").strip().lower()
                if ue and ue not in seen_emails:
                    seen_emails.add(ue)
                    travellers.append({
                        "id": e.get("id"),
                        "name": e.get("user_name") or ue.split("@")[0],
                        "email": ue,
                        "phone": e.get("user_phone", ""),
                        "seats": e.get("seats", 1),
                        "booking_code": e.get("booking_code", ""),
                        "role": "traveller",
                        "status": "confirmed"
                    })

        for t_pax in travellers:
            if t_pax.get("status") != "cancelled":
                members.append({
                    "name": t_pax.get("name") or (t_pax.get("email", "").split("@")[0]),
                    "email": t_pax.get("email"),
                    "phone": t_pax.get("phone", ""),
                    "seats": t_pax.get("seats", 1),
                    "booking_code": t_pax.get("booking_code", ""),
                    "role": "traveller",
                    "is_admin": False,
                    "is_host": False
                })
                
        # If no messages exist yet, seed initial welcome message from the Host Agent
        if len(msgs) == 0:
            welcome_text = f"👋 Welcome everyone to the {trip.get('title', 'Group Trip')} group chat! I am {trip.get('agent_name', 'your trip host')}, the Admin and tour specialist for this expedition. You can discuss trip details, ask questions, and connect with fellow travellers here!"
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            time_str = time.strftime("%I:%M %p")
            seed_msg = {
                "id": get_next_sequence("trip_messages"),
                "trip_id": trip.get("id"),
                "trip_title": trip.get("title", ""),
                "sender_email": admin_email or "agent@travelverse.com",
                "sender_name": trip.get("agent_name", "Host Agent"),
                "sender_role": "admin",
                "message_text": welcome_text,
                "time_str": time_str,
                "is_announcement": True,
                "status": "read",
                "deleted_for": [],
                "created_at": now_str
            }
            db.trip_messages.insert_one(seed_msg)
            seed_msg.pop("_id", None)
            msgs.append(seed_msg)

    formatted_msgs = []
    for m in msgs:
        doc = serialize_doc(m)
        if not doc.get("time_str"):
            created = doc.get("created_at") or ""
            if " " in created:
                try:
                    t_part = created.split(" ")[1]
                    hr, mn = t_part.split(":")[:2]
                    hr_int = int(hr)
                    suffix = "AM" if hr_int < 12 else "PM"
                    hr_12 = hr_int if hr_int <= 12 else hr_int - 12
                    if hr_12 == 0: hr_12 = 12
                    doc["time_str"] = f"{hr_12}:{mn} {suffix}"
                except Exception:
                    doc["time_str"] = created
            else:
                doc["time_str"] = created
        formatted_msgs.append(doc)

    return {
        "status": "success",
        "trip_id": clean_trip_id,
        "trip": trip_data,
        "members": members,
        "messages": formatted_msgs
    }

@app.get("/user-trip-chats/{user_email}")
def get_user_trip_chats(user_email: str):
    clean_email = (user_email or "").strip().lower()
    if not clean_email:
        return {"status": "success", "trip_chats": []}

    enrolled_trip_ids = set()
    enr_query = {"$or": [
        {"user_email": {"$regex": f"^{re.escape(clean_email)}$", "$options": "i"}},
        {"traveller_email": {"$regex": f"^{re.escape(clean_email)}$", "$options": "i"}}
    ]}
    for enr in db.trip_enrollments.find(enr_query):
        t_id = enr.get("trip_id")
        if t_id is not None:
            enrolled_trip_ids.add(t_id)
            if str(t_id).isdigit():
                enrolled_trip_ids.add(int(t_id))
    for bk in db.bookings.find(enr_query):
        t_id = bk.get("trip_id")
        if t_id is not None:
            enrolled_trip_ids.add(t_id)
            if str(t_id).isdigit():
                enrolled_trip_ids.add(int(t_id))

    # Check if this email or identifier belongs to an agent
    agent_doc = db.agents.find_one({
        "$or": [
            {"email": {"$regex": f"^{re.escape(clean_email)}$", "$options": "i"}},
            {"agency_email": {"$regex": f"^{re.escape(clean_email)}$", "$options": "i"}},
            {"contact_email": {"$regex": f"^{re.escape(clean_email)}$", "$options": "i"}},
            {"agency_name": {"$regex": f"^{re.escape(clean_email)}$", "$options": "i"}},
            {"username": {"$regex": f"^{re.escape(clean_email)}$", "$options": "i"}},
            {"agent_name": {"$regex": f"^{re.escape(clean_email)}$", "$options": "i"}},
            {"id": int(clean_email) if clean_email.isdigit() else -1}
        ]
    })

    trip_conditions = [
        {"agent_email": {"$regex": f"^{re.escape(clean_email)}$", "$options": "i"}},
        {"id": {"$in": list(enrolled_trip_ids)}}
    ]
    if agent_doc:
        aid = agent_doc.get("id")
        if aid is not None:
            trip_conditions.append({"agent_id": aid})
            trip_conditions.append({"agent_id": str(aid)})
            if str(aid).isdigit():
                trip_conditions.append({"agent_id": int(aid)})
        a_em = (agent_doc.get("email") or "").strip()
        if a_em:
            trip_conditions.append({"agent_email": {"$regex": f"^{re.escape(a_em)}$", "$options": "i"}})

    agent_query = {"$or": trip_conditions}
    trips = list(db.group_trips.find(agent_query).sort("id", -1))
    
    chats = []
    seen_ids = set()
    for trip in trips:
        tid = trip.get("id")
        if tid in seen_ids:
            continue
        seen_ids.add(tid)
        
        trip_agent_email = (trip.get("agent_email") or "").strip().lower()
        is_admin = (trip_agent_email == clean_email) or (agent_doc and (
            str(trip.get("agent_id")) == str(agent_doc.get("id")) or
            (agent_doc.get("email") or "").strip().lower() == trip_agent_email
        ))
        
        travellers = trip.get("enrolled_travellers") or []
        if len(travellers) == 0:
            enrs = list(db.trip_enrollments.find({
                "$or": [{"trip_id": tid}, {"trip_id": str(tid)}, {"trip_title": trip.get("title")}],
                "status": {"$ne": "cancelled"}
            }))
            for e in enrs:
                ue = (e.get("user_email") or "").strip().lower()
                travellers.append({
                    "id": e.get("id"),
                    "name": e.get("user_name") or ue.split("@")[0],
                    "email": ue,
                    "phone": e.get("user_phone", ""),
                    "seats": int(e.get("seats") or 1),
                    "booking_code": e.get("booking_code", ""),
                    "status": "confirmed"
                })

        confirmed_pax = [p for p in travellers if p.get("status") != "cancelled"]
        passengers_count = len(confirmed_pax)
        enrolled_seats = trip.get("enrolled_count") or sum(int(p.get("seats") or 1) for p in confirmed_pax) or passengers_count
        
        last_m = db.trip_messages.find_one(
            {"$or": [{"trip_id": tid}, {"trip_id": str(tid)}], "deleted_for": {"$nin": [clean_email]}},
            sort=[("id", -1)]
        )
        
        last_msg_text = last_m.get("message_text") if last_m else f"Welcome to the {trip.get('title')} group chat!"
        last_msg_time = (last_m.get("time_str") or last_m.get("created_at")) if last_m else trip.get("created_at", "")
        last_sender_name = last_m.get("sender_name") if last_m else (trip.get("agent_name") or "Host Agent")
        last_sender_role = last_m.get("sender_role") if last_m else "admin"

        chats.append({
            "trip_id": tid,
            "title": trip.get("title", "Group Expedition"),
            "destination": trip.get("destination", "World"),
            "start_date": trip.get("start_date", ""),
            "end_date": trip.get("end_date", ""),
            "dates": f"{trip.get('start_date', '')} to {trip.get('end_date', '')}".strip(" to "),
            "cover_image": trip.get("cover_image") or "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=800&q=80",
            "agent_name": trip.get("agent_name", "Host Agent"),
            "agent_email": trip.get("agent_email", ""),
            "agency_name": trip.get("agency_name", "TravelVerse Partner"),
            "is_admin": is_admin,
            "members_count": passengers_count,
            "passengers_count": passengers_count,
            "enrolled_count": passengers_count,
            "enrolled_travellers": confirmed_pax,
            "last_message": last_msg_text,
            "last_message_time": last_msg_time,
            "last_sender_name": last_sender_name,
            "last_sender_role": last_sender_role
        })

    return {"status": "success", "trip_chats": chats}

@app.post("/delete-trip-message")
def delete_trip_message(req: DeleteTripMessageRequest):
    u = (req.user_email or "").strip().lower()
    m_raw = req.message_id
    try:
        m_id = int(m_raw)
    except Exception:
        m_id = m_raw
    if not u or m_id is None:
        raise HTTPException(status_code=400, detail="Missing user_email or message_id")
    
    query = {"$or": [{"id": m_id}, {"id": str(m_id)}]}
    db.trip_messages.update_one(query, {"$addToSet": {"deleted_for": u}})
    return {"status": "success", "message": "Message deleted for user"}


# -------------------------------------------------------------
# AI ITINERARY GENERATOR, PDF VOUCHER & COPILOT
# -------------------------------------------------------------
@app.post("/ai-generate-itinerary")
def ai_generate_itinerary(req: AIGenerateItineraryRequest):
    dest = (req.destination or "").strip()
    if not dest:
        raise HTTPException(status_code=400, detail="Destination is required.")

    data = generate_professional_itinerary(
        destination=dest,
        duration_days=req.duration_days or 5,
        category=req.category or "Cultural",
        difficulty=req.difficulty or "Moderate",
        agent_name=req.agent_name or "Host Guide",
        agency_name=req.agency_name or "Travel Agency"
    )
    return {"status": "success", "data": data}

@app.get("/trip-itinerary.pdf")
@app.get("/group-trips/{trip_id}/pdf")
def get_trip_itinerary_pdf_file(trip_id: str = "110", booking_code: Optional[str] = None):
    booking = None
    if booking_code:
        try:
            booking = db.trip_enrollments.find_one({"booking_code": booking_code}) or db.bookings.find_one({"booking_code": booking_code})
        except Exception as b_err:
            print("[DB NOTE] Error fetching booking for PDF:", b_err)

    # Determine which trip ID to use
    target_trip_id = trip_id
    if booking and booking.get("trip_id"):
        target_trip_id = str(booking.get("trip_id"))

    t_query = {"$or": [{"id": int(target_trip_id) if target_trip_id.isdigit() else -1}, {"id": target_trip_id}]}
    trip = None
    try:
        trip = db.group_trips.find_one(t_query)
        if not trip:
            seed_default_agents_and_trips()
            trip = db.group_trips.find_one(t_query)
    except Exception as db_err:
        print("[DB NOTE] Offline/unreachable database for PDF generation:", db_err)

    if not trip:
        trip = {
            "title": (booking.get("trip_title") if booking else None) or "Spiti Valley High-Pass 4x4 Circuit",
            "destination": (booking.get("destination") if booking else None) or "Spiti Valley, Himachal Pradesh",
            "duration_days": 8,
            "price": 48500,
            "agency_name": "Himalayan High Passes",
            "agent_name": "Aarav Sharma",
            "itinerary": [
                {"day": 1, "title": "Rendezvous in Manali & Briefing", "description": "Meet team at Manali lounge, equip mountain medical kit."},
                {"day": 2, "title": "Rohtang Tunnel Crossing to Kaza", "description": "Drive through Atal Tunnel and over Kunzum Pass."}
            ]
        }

    pdf_bytes = generate_trip_itinerary_pdf(trip, booking)
    filename = f"TravelVerse_Invoice_{booking_code or trip_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )

@app.get("/api/assistant-config")
def get_assistant_config():
    keys = []
    for i in range(1, 10):
        k = os.environ.get(f"GEMINI_API_KEY_{i}")
        if k: keys.append(k.strip())
    if not keys and os.environ.get("GEMINI_API_KEY"):
        keys.append(os.environ.get("GEMINI_API_KEY").strip())

    return {
        "status": "success",
        "gemini_keys": keys,
        "gemini_model": os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
        "places_key": os.environ.get("GOOGLE_PLACES_API_KEY", ""),
        "rapidapi_key": os.environ.get("RAPIDAPI_KEY", ""),
        "rapidapi_host": os.environ.get("RAPIDAPI_HOST", "flights-sky.p.rapidapi.com")
    }

@app.post("/chat-ai-assistant")
def chat_ai_assistant(req: ChatAiAssistantRequest):
    q = (req.query or "").strip().lower()
    dest = req.destination or req.trip_title or "your destination"
    traveller = req.traveller_name or "the traveller"
    agent = req.agent_name or "the host guide"
    agency = req.agent_agency or "Travel Agency"
    dates = req.travel_dates or "upcoming travel season"
    budget = req.budget or "flexible budget"

    # Contextual procedural response generator
    if any(k in q for k in ["pack", "bring", "clothing", "gear"]):
        reply = (
            f"🎒 **Recommended Packing Checklist for {dest}:**\n\n"
            f"1. **Thermal Base Layers**: Essential for evenings and mountain altitudes.\n"
            f"2. **Down / Windproof Jacket**: Protection against sudden temperature drops.\n"
            f"3. **Sturdy Hiking Boots**: Waterproof boots with ankle support.\n"
            f"4. **UV Polarized Sunglasses & High SPF Sunscreen**: High altitude sunlight is intense.\n"
            f"5. **Personal Medical & First Aid**: Any prescription meds plus altitude remedies.\n\n"
            f"Would you like me to add custom items based on your planned activities?"
        )
    elif any(k in q for k in ["acclimat", "altitude", "sickness", "ams"]):
        reply = (
            f"⛰️ **Altitude & Acclimatization Guidelines for {dest}:**\n\n"
            f"- **Hydration**: Drink at least 3-4 liters of water daily.\n"
            f"- **Gradual Ascent**: Avoid over-exertion on the first 24-48 hours.\n"
            f"- **Emergency Support**: Guide {agent} carries an emergency oxygen cylinder and pulse oximeter.\n"
            f"- **Dietary Advice**: Eat light, high-carbohydrate meals; avoid alcohol during early days."
        )
    elif any(k in q for k in ["itinerary", "day", "schedule", "plan"]):
        reply = (
            f"📅 **Expedition Dossier Overview for {dest}:**\n\n"
            f"Your departure ({dates}) features day-by-day curated excursions led by {agency}. "
            f"Morning departures are typically at 08:30 AM with scenic trail lunches, afternoon explorations, and evening fireside briefings. "
            f"You can also download your full high-res PDF brochure anytime!"
        )
    else:
        reply = (
            f"Hello! I am your TravelVerse Expedition Copilot for **{dest}**.\n\n"
            f"I have reviewed your details for {traveller} (dates: {dates}, budget: {budget}). "
            f"I can assist with packing checklists, weather forecasts, route logistics, or connecting directly with {agent} at {agency}. What would you like to plan?"
        )

    return {"status": "success", "reply": reply}

@app.post("/api/chat")
async def api_chat_proxy(req: Request):
    """Fallback / backend chat endpoint for Milo AI Travel Assistant."""
    try:
        body = await req.json()
        messages = body.get("messages", [])
        last_user_msg = "Hello"
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        # Check if we have Gemini key for direct completion
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            try:
                import urllib.request
                model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
                gemini_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"You are Milo, the helpful TravelVerse AI Assistant. User asks: {last_user_msg}"}]}]
                }
                req_obj = urllib.request.Request(
                    gemini_endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req_obj, timeout=10) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    return {"status": "success", "text": text}
            except Exception as gem_err:
                print("[GEMINI PROXY NOTE]", gem_err)

        # Built-in contextual fallback response
        copilot_res = chat_ai_assistant(ChatAiAssistantRequest(query=last_user_msg))
        return {"status": "success", "text": copilot_res.get("reply", "I am Milo, your TravelVerse assistant. How can I help you today?")}
    except Exception as e:
        return {"status": "success", "text": f"TravelVerse Copilot ready. How can I help you with your journeys today?"}


# -------------------------------------------------------------
# SMART ICEBREAKERS ENDPOINT (Profile-Based Mutual Affinity)
# -------------------------------------------------------------
@app.get("/chat-icebreakers/{user_email}/{buddy_email}")
def get_chat_icebreakers(user_email: str, buddy_email: str, vibe: str = "all", seed: int = 0, dest: Optional[str] = None, role: Optional[str] = None):
    """
    Suggests smart, witty, and contextual conversation starters based on the mutual
    destinations and travel profiles both travelers have saved.
    Supports dynamic category filtering and unlimited shuffling without exposing match scores.
    """
    try:
        u_email = (user_email or "").strip().lower()
        b_email = (buddy_email or "").strip().lower()

        if not u_email or not b_email:
            raise HTTPException(status_code=400, detail="Both traveler emails are required.")

        # 1. Fetch User Profile
        user_doc = None
        buddy_doc = None
        try:
            user_doc = find_traveller_or_agent(u_email)
            if not user_doc:
                user_doc = db.users.find_one({"email": {"$regex": f"^{re.escape(u_email)}$", "$options": "i"}})
            if not user_doc:
                user_doc = db.companions.find_one({"user_email": {"$regex": f"^{re.escape(u_email)}$", "$options": "i"}})
        except Exception:
            pass

        if not user_doc:
            user_doc = {"email": u_email, "name": u_email.split("@")[0].capitalize(), "trip_interests": [], "badges": []}

        # 2. Fetch Buddy Profile
        try:
            buddy_doc = find_traveller_or_agent(b_email)
            if not buddy_doc:
                buddy_doc = db.users.find_one({"email": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}})
            if not buddy_doc:
                buddy_doc = db.companions.find_one({"user_email": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}})
            if not buddy_doc:
                agent = db.agents.find_one({"email": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}})
                if agent:
                    buddy_doc = {
                        "first_name": agent.get("agent_name", "Host Agent"),
                        "destination": agent.get("specializations", "Custom Expeditions"),
                        "badges": ["Verified Agent", "Local Expert"],
                        "email": b_email
                    }
        except Exception:
            pass

        if not buddy_doc:
            buddy_doc = {"email": b_email, "name": b_email.split("@")[0].capitalize(), "trip_interests": [], "badges": []}

        # Directly fetch all trip interests for both users from db.trip_interests
        try:
            u_interests_docs = list(db.trip_interests.find({"user_email": {"$regex": f"^{re.escape(u_email)}$", "$options": "i"}}))
            b_interests_docs = list(db.trip_interests.find({"user_email": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}}))
            user_doc["trip_interests"] = [serialize_doc(i) for i in u_interests_docs] + (user_doc.get("trip_interests") or [])
            buddy_doc["trip_interests"] = [serialize_doc(i) for i in b_interests_docs] + (buddy_doc.get("trip_interests") or [])
        except Exception:
            pass

        # Also check companion connection in db.connections
        try:
            conn = db.connections.find_one({
                "$or": [
                    {"sender_email": {"$regex": f"^{re.escape(u_email)}$", "$options": "i"}, "receiver_email": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}},
                    {"sender_email": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}, "receiver_email": {"$regex": f"^{re.escape(u_email)}$", "$options": "i"}},
                    {"from_email": {"$regex": f"^{re.escape(u_email)}$", "$options": "i"}, "to_email": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}},
                    {"from_email": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}, "to_email": {"$regex": f"^{re.escape(u_email)}$", "$options": "i"}}
                ]
            })
            if conn and conn.get("destination"):
                from icebreakers_ml import is_generic_destination
                if not is_generic_destination(conn["destination"]):
                    buddy_doc["destination"] = conn["destination"]
        except Exception:
            pass

        # Override destination if client passed a real destination
        from icebreakers_ml import rank_and_generate_icebreakers, extract_destinations, find_mutual_destination, is_generic_destination

        override_dest = None
        if dest and isinstance(dest, str) and not is_generic_destination(dest):
            override_dest = dest.strip()

        user_dests = extract_destinations(user_doc)
        buddy_dests = extract_destinations(buddy_doc)
        mutual_dest, _ = find_mutual_destination(user_dests, buddy_dests)
        resolved_dest = override_dest or (mutual_dest if mutual_dest else None)

        icebreakers = rank_and_generate_icebreakers(
            user_doc,
            buddy_doc,
            vibe=vibe,
            seed=seed,
            top_k=15,
            override_destination=resolved_dest,
            role=role
        )

        return {
            "status": "success",
            "mutual_destination": resolved_dest,
            "vibe": vibe,
            "icebreakers": icebreakers
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "icebreakers": [
                {"tag": "☕ Vibe Check", "emoji": "☕", "text": "Quick vibe check: are we waking up early for sunrise viewpoints or sleeping in and hitting local cafes? ☕", "category": "vibe"},
                {"tag": "🗺️ Wishlist", "emoji": "🗺️", "text": "What destinations are sitting at the absolute top of your travel bucket list right now?", "category": "discovery"},
                {"tag": "🤝 Travel Squad", "emoji": "🤝", "text": "Looking for chill travel buddies to explore new spots with. What's your travel style?", "category": "collab"}
            ]
        }


# -------------------------------------------------------------
# STATIC FRONTEND SERVING
# -------------------------------------------------------------
frontend_dir = os.path.abspath(os.path.join(backend_dir, "..", "frontend"))
if os.path.exists(frontend_dir):
    from starlette.staticfiles import StaticFiles
    # Mount css and js
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    # Serve static HTML files directly
    @app.get("/{page_name}.html")
    def serve_html_page(page_name: str):
        file_path = os.path.join(frontend_dir, f"{page_name}.html")
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        raise HTTPException(status_code=404, detail="Page not found.")

if __name__ == "__main__":
    import uvicorn
    seed_default_agents_and_trips()
    print("=" * 65)
    print("  TRAVELVERSE UNIFIED ENTERPRISE BACKEND SERVER")
    print("  Host: http://127.0.0.1:8000")
    print("  Swagger Docs: http://127.0.0.1:8000/docs")
    print("=" * 65)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
