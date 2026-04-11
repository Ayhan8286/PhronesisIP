"""Seed the development database with a test firm and sample patents."""
import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_HEi1bZ7MLkcV@ep-dark-feather-am2o5qga.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require"

def seed():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # Dev firm (matches get_dev_user() firm_id)
    DEV_FIRM_ID = "00000000-0000-0000-0000-000000000010"
    DEV_USER_ID = "00000000-0000-0000-0000-000000000001"

    print("Seeding dev firm...")
    cur.execute("""
        INSERT INTO firms (id, name, clerk_org_id, settings)
        VALUES (%s, 'Dev Law Firm LLP', 'org_dev', '{}')
        ON CONFLICT (clerk_org_id) DO NOTHING
    """, (DEV_FIRM_ID,))

    print("Seeding dev user...")
    cur.execute("""
        INSERT INTO users (id, clerk_user_id, firm_id, email, full_name, role)
        VALUES (%s, 'dev_user', %s, 'dev@patentiq.com', 'Dev Attorney', 'admin')
        ON CONFLICT (clerk_user_id) DO NOTHING
    """, (DEV_USER_ID, DEV_FIRM_ID))

    # Sample patent families
    families = [
        ("f0000001-0000-4000-8000-000000000001", "AI Inspection Platform"),
        ("f0000002-0000-4000-8000-000000000002", "Post-Quantum Security Suite"),
        ("f0000003-0000-4000-8000-000000000003", "MedDevice Material Science"),
        ("f0000004-0000-4000-8000-000000000004", "Autonomous Vehicle Sensor Suite"),
    ]
    print("Seeding patent families...")
    for fid, fname in families:
        cur.execute("""
            INSERT INTO patent_families (id, firm_id, family_name)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (fid, DEV_FIRM_ID, fname))

    # Sample patents
    patents = [
        ("a0000001-0000-4000-8000-000000000001", "US 17/234,567", None,
         "Neural Network-Based Semiconductor Defect Detection System",
         "A system using deep convolutional neural networks to detect and classify defects in semiconductor wafer images captured during optical inspection, enabling real-time quality control in fabrication facilities.",
         "pending", "2025-11-15", None, "f0000001-0000-4000-8000-000000000001",
         '[{"first_name": "James", "last_name": "Chen"}, {"first_name": "Sarah", "last_name": "Park"}]',
         "TechVision Corp."),
        ("a0000002-0000-4000-8000-000000000002", "US 17/345,678", "US 11,999,888",
         "Quantum-Resistant Cryptographic Key Exchange Protocol",
         "A lattice-based key exchange protocol resistant to quantum computing attacks, implementing a novel approach to post-quantum cryptography suitable for resource-constrained IoT devices.",
         "granted", "2025-09-22", "2026-02-14", "f0000002-0000-4000-8000-000000000002",
         '[{"first_name": "Alex", "last_name": "Rivera"}, {"first_name": "Dr. Maria", "last_name": "Kowalski"}]',
         "SecureQ Inc."),
        ("a0000003-0000-4000-8000-000000000003", "US 17/456,789", None,
         "Bio-Degradable Polymer Composite for Medical Implants",
         "A biodegradable polymer composite comprising polylactic acid and hydroxyapatite nanoparticles for use in orthopedic implants, featuring controlled degradation rates matching natural bone regeneration.",
         "pending", "2025-12-03", None, "f0000003-0000-4000-8000-000000000003",
         '[{"first_name": "Dr. Emily", "last_name": "Watson"}]',
         "BioMed Innovations LLC"),
        ("a0000004-0000-4000-8000-000000000004", "US 17/567,890", None,
         "Autonomous Vehicle LIDAR Calibration Method",
         "An automated calibration method for multi-beam LIDAR sensors mounted on autonomous vehicles, using ground truth point cloud data and machine learning to compensate for angular drift.",
         "abandoned", "2025-06-18", None, "f0000004-0000-4000-8000-000000000004",
         '[{"first_name": "Mike", "last_name": "Johnson"}]',
         "AutoDrive Technologies"),
        ("a0000005-0000-4000-8000-000000000005", "US 17/678,901", None,
         "Machine Learning Pipeline for Drug Discovery Optimization",
         "A distributed machine learning pipeline that integrates molecular dynamics simulation with graph neural networks to predict drug-target binding affinity and optimize lead compound selection.",
         "pending", "2026-01-07", None, None,
         '[{"first_name": "Dr. Lisa", "last_name": "Huang"}, {"first_name": "Dr. Robert", "last_name": "Kim"}]',
         "PharmaAI Corp."),
    ]

    print("Seeding sample patents...")
    for p in patents:
        cur.execute("""
            INSERT INTO patents (id, firm_id, application_number, patent_number, title, abstract, status, filing_date, grant_date, family_id, inventors, assignee)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT DO NOTHING
        """, (p[0], DEV_FIRM_ID, p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10]))

    # Sample claims for first patent
    claims_patent1 = [
        (1, True, "A system for detecting defects in semiconductor wafers, comprising: an optical inspection module configured to capture images of a wafer surface; a processing unit comprising a convolutional neural network trained to identify defect patterns; and a classification engine that categorizes detected defects into predefined categories including scratches, particles, and film irregularities."),
        (2, False, "The system of claim 1, wherein the convolutional neural network comprises at least five convolutional layers with batch normalization."),
        (3, True, "A method for real-time semiconductor wafer inspection, comprising: receiving a sequence of wafer images from an optical sensor; preprocessing each image to normalize illumination variations; applying a trained deep learning model to generate a defect probability map; and outputting classified defect locations with confidence scores exceeding a configurable threshold."),
        (4, False, "The method of claim 3, wherein preprocessing includes adaptive histogram equalization."),
        (5, False, "The method of claim 3, further comprising transmitting defect data to a manufacturing execution system for automated process control."),
    ]
    print("Seeding sample claims...")
    for cn, indep, ctext in claims_patent1:
        cur.execute("""
            INSERT INTO patent_claims (patent_id, claim_number, is_independent, claim_text)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, ("a0000001-0000-4000-8000-000000000001", cn, indep, ctext))

    # Sample office actions
    print("Seeding sample office actions...")
    cur.execute("""
        INSERT INTO office_actions (id, patent_id, action_type, mailing_date, response_deadline, status, extracted_text, rejections)
        VALUES
        ('0a000001-0000-4000-8000-000000000001', 'a0000001-0000-4000-8000-000000000001', 'Non-Final Rejection', '2026-03-01', '2026-06-01', 'pending',
         'Claims 1-5 are rejected under 35 U.S.C. 103 as being obvious over Smith (US 10,111,222) in view of Jones (US 10,333,444). Smith discloses a semiconductor inspection system using image processing. Jones teaches the use of CNN for pattern recognition in manufacturing. It would have been obvious to combine the teachings.',
         '[{"type": "103", "claims": [1,2,3,4,5], "references": ["Smith US 10,111,222", "Jones US 10,333,444"]}]'::jsonb),
        ('0a000002-0000-4000-8000-000000000002', 'a0000002-0000-4000-8000-000000000002', 'Final Rejection', '2026-02-15', '2026-05-15', 'pending',
         'Claims 1-3 are rejected under 35 U.S.C. 102(a)(1) as being anticipated by Lee (US 10,123,456). Lee discloses a cryptographic key exchange protocol using lattice-based algorithms resistant to quantum attacks.',
         '[{"type": "102", "claims": [1,2,3], "references": ["Lee US 10,123,456"]}]'::jsonb),
        ('0a000003-0000-4000-8000-000000000003', 'a0000003-0000-4000-8000-000000000003', 'Non-Final Rejection', '2026-01-20', '2026-04-20', 'responded',
         'Claims 3-7 are rejected under 35 U.S.C. 112(b) as being indefinite. The terms "controlled degradation rates" and "matching natural bone regeneration" lack clear antecedent basis.',
         '[{"type": "112", "claims": [3,4,5,6,7], "references": []}]'::jsonb)
        ON CONFLICT DO NOTHING
    """)

    # Prior art references
    print("Seeding prior art references...")
    cur.execute("""
        INSERT INTO prior_art_references (patent_id, reference_number, reference_title, reference_abstract, reference_type, relevance_score, cited_by_examiner)
        VALUES
        ('a0000001-0000-4000-8000-000000000001', 'US 9,876,543', 'Deep Learning-Based Visual Inspection System for Semiconductor Wafers', 'A system comprising a convolutional neural network configured to receive wafer images and detect defect patterns including scratches, particles, and film irregularities.', 'patent', 0.94, true),
        ('a0000001-0000-4000-8000-000000000001', 'US 10,234,567', 'Automated Optical Inspection Using Transfer Learning', 'A transfer learning module that adapts a pre-trained image classification model to a domain-specific inspection task using a limited training dataset.', 'patent', 0.87, true),
        ('a0000001-0000-4000-8000-000000000001', 'US 11,345,678', 'Multi-Sensor Fusion Method for Manufacturing Quality Control', 'Combining data from optical sensors, thermal cameras, and acoustic emission detectors to generate a unified quality assessment score.', 'patent', 0.72, false)
        ON CONFLICT DO NOTHING
    """)

    cur.close()
    conn.close()
    print("Done! Database seeded with sample data.")

if __name__ == "__main__":
    seed()
