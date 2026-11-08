import os
from pymongo import MongoClient
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def synchronize_equipment():

    print("Connecting to MongoDB...")

    mongo = MongoClient(os.getenv("MONGO_URI"))

    collection = mongo[
        os.getenv("MONGO_DATABASE")
    ][
        os.getenv("MONGO_COLLECTION")
    ]

    print("Connecting to MariaDB...")

    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        database=os.getenv("MYSQL_DATABASE"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD")
    )

    cursor = connection.cursor()

    pipeline = [
        {
            "$group": {
                "_id": "$equipment_id",
                "model": {"$first": "$model"},
                "record_count": {"$sum": 1}
            }
        },
        {
            "$sort": {"_id": 1}
        }
    ]

    records = list(collection.aggregate(pipeline))

    print(f"Found {len(records)} equipment units.")

    query = """
        INSERT INTO equipment (
            equipment_id,
            model,
            warranty_expiration,
            warranty_status,
            telemetry_record_count,
            metadata_source
        )
        VALUES (%s, %s, NULL, 'UNKNOWN', %s,
                'professor_telemetry')

        ON DUPLICATE KEY UPDATE
            model = VALUES(model),
            telemetry_record_count = VALUES(telemetry_record_count),
            metadata_source = 'professor_telemetry'
    """

    try:
        for record in records:

            equipment_id = record["_id"]
            model = record["model"]
            count = record["record_count"]

            if not equipment_id or not model:
                continue

            cursor.execute(
                query,
                (equipment_id, model, count)
            )

            print(
                f"Synced: {equipment_id} | "
                f"{model} | Records: {count}"
            )

        connection.commit()

        print("\nSynchronization successful!")
        print(f"Total equipment processed: {len(records)}")

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
        mongo.close()


if __name__ == "__main__":
    synchronize_equipment()
