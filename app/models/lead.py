from datetime import datetime
from app.extensions import db


class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer,
        db.ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False
    )

    campaign_id = db.Column(
        db.Integer,
        db.ForeignKey('campaigns.id', ondelete='CASCADE'),
        nullable=False
    )

    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    company_name = db.Column(db.String(255), nullable=True)
    job_title = db.Column(db.String(255), nullable=True)
    city      = db.Column(db.String(100), nullable=True)
    state     = db.Column(db.String(50),  nullable=True)

    numero_1 = db.Column(db.String(30), nullable=False)
    numero_2 = db.Column(db.String(30), nullable=True)
    numero_3 = db.Column(db.String(30), nullable=True)
    numero_4 = db.Column(db.String(30), nullable=True)
    numero_5 = db.Column(db.String(30), nullable=True)
    numero_6 = db.Column(db.String(30), nullable=True)
    numero_7 = db.Column(db.String(30), nullable=True)
    numero_8 = db.Column(db.String(30), nullable=True)

    status = db.Column(db.String(50), nullable=False, default='new')
    notes = db.Column(db.Text, nullable=True)

    import_order = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    company = db.relationship('Company', back_populates='leads', lazy=True)
    campaign = db.relationship('Campaign', back_populates='leads', lazy=True)
    calls = db.relationship('Call', back_populates='lead', lazy=True, cascade='all, delete-orphan')

    def get_primary_phone(self):
        return self.numero_1

    def get_all_phones(self):
        return [
            phone for phone in [
                self.numero_1,
                self.numero_2,
                self.numero_3,
                self.numero_4,
                self.numero_5,
                self.numero_6,
                self.numero_7,
                self.numero_8,
            ] if phone
        ]