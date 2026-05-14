// =============================================================================
// MongoDB initialization — simulates wearable / app telemetry store
// =============================================================================
// Mirrors the Kaggle Fitbit Fitness Tracker dataset (Möbius release).
// =============================================================================

db = db.getSiblingDB("wellness_telemetry");

// ----- Collections ----------------------------------------------------------
db.createCollection("user_profiles", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["user_id", "created_at"],
            properties: {
                user_id:        { bsonType: "string" },
                age:            { bsonType: "int", minimum: 0, maximum: 120 },
                gender:         { enum: ["M", "F", "NB", "U"] },
                dietary_pref:   { bsonType: "string" },
                created_at:     { bsonType: "date" }
            }
        }
    }
});

db.createCollection("daily_activity");        // steps, distance, calories
db.createCollection("heart_rate");            // minute-level HR readings
db.createCollection("sleep_records");         // nightly sleep stages
db.createCollection("ingestion_audit");       // raw API audit trail

// ----- Indexes for query performance ----------------------------------------
db.daily_activity.createIndex({ user_id: 1, date: -1 });
db.heart_rate.createIndex({ user_id: 1, timestamp: -1 });
db.sleep_records.createIndex({ user_id: 1, sleep_start: -1 });
db.sleep_records.createIndex({ user_id: 1, sleep_start: 1 }, { unique: true });

// ----- Seed roles for governance --------------------------------------------
db.createRole({
    role: "analyst_read",
    privileges: [
        { resource: { db: "wellness_telemetry", collection: "" },
          actions: [ "find" ] }
    ],
    roles: []
});

print("✅ wellness_telemetry initialized with 5 collections and indexes.");
