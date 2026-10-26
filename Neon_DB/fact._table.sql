CREATE TABLE "fact_admission" (
	"admission_id" varchar(50) PRIMARY KEY,
	"patient_id" varchar(50),
	"doctor_id" varchar(50),
	"disease_id" varchar(50),
	"department_id" varchar(50),
	"admit_date" date,
	"discharge_date" date,
	"severity" varchar(50) NOT NULL,
	"sample_id" integer,
	"load_date" timestamp DEFAULT CURRENT_TIMESTAMP,
	"batch_id" varchar(50),
	"source_system" varchar(50) DEFAULT 'HIS'
);
CREATE UNIQUE INDEX "fact_admission_pkey" ON "fact_admission" ("admission_id");
ALTER TABLE "fact_admission" ADD CONSTRAINT "fact_admission_department_id_fkey" FOREIGN KEY ("department_id") REFERENCES "dim_departments"("department_id") ON DELETE CASCADE;
ALTER TABLE "fact_admission" ADD CONSTRAINT "fact_admission_disease_id_fkey" FOREIGN KEY ("disease_id") REFERENCES "dim_diseases"("disease_id") ON DELETE CASCADE;
ALTER TABLE "fact_admission" ADD CONSTRAINT "fact_admission_doctor_id_fkey" FOREIGN KEY ("doctor_id") REFERENCES "dim_doctors"("doctor_id") ON DELETE CASCADE;
ALTER TABLE "fact_admission" ADD CONSTRAINT "fact_admission_patient_id_fkey" FOREIGN KEY ("patient_id") REFERENCES "dim_patients"("patient_id") ON DELETE CASCADE;
ALTER TABLE "fact_admission" ADD CONSTRAINT "fact_admission_sample_id_fkey" FOREIGN KEY ("sample_id") REFERENCES "mtsamples"("sample_id") ON DELETE CASCADE;

---

CREATE TABLE "fact_billing" (
	"billingid" varchar(50) PRIMARY KEY,
	"admissionid" varchar(50),
	"patientid" varchar(50),
	"insuranceprovider" varchar(50) NOT NULL,
	"totalamount" varchar(20) NOT NULL,
	"insurancecoveredamount" varchar(20) NOT NULL,
	"patientresponsibility" varchar(20) NOT NULL,
	"paymentstatus" varchar(15),
	"billingdate" date NOT NULL,
	"load_date" timestamp DEFAULT CURRENT_TIMESTAMP,
	"batch_id" varchar(50),
	"source_system" varchar(50) DEFAULT 'Billing App',
	CONSTRAINT "fact_billing_paymentstatus_check" CHECK (((paymentstatus)::text = ANY ((ARRAY['Paid'::character varying, 'Pending'::character varying, 'Appealed'::character varying])::text[])))
);
CREATE UNIQUE INDEX "fact_billing_pkey" ON "fact_billing" ("billingid");
ALTER TABLE "fact_billing" ADD CONSTRAINT "fact_billing_admissionid_fkey" FOREIGN KEY ("admissionid") REFERENCES "fact_admission"("admission_id") ON DELETE CASCADE;
ALTER TABLE "fact_billing" ADD CONSTRAINT "fact_billing_patientid_fkey" FOREIGN KEY ("patientid") REFERENCES "dim_patients"("patient_id") ON DELETE CASCADE;
