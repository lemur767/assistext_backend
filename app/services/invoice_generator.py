# app/services/invoice_generator.py
"""
Invoice generator service for creating and managing billing invoices
Handles PDF generation, email delivery, and invoice management
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from io import BytesIO
import uuid

# PDF generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# Email
from flask_mail import Message as EmailMessage
from flask import current_app, render_template

from app.extensions import db, mail
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.subscription import Subscription
from app.models.user import User
from app.models.payment import Payment
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

class InvoiceGenerator:
    """Service for generating and managing invoices"""
    
    @classmethod
    def create_subscription_invoice(cls, subscription_id: str, billing_period_start: datetime, 
                                  billing_period_end: datetime) -> Dict[str, Any]:
        """Create invoice for subscription billing period"""
        try:
            subscription = Subscription.query.get(subscription_id)
            if not subscription:
                return {'success': False, 'error': 'Subscription not found'}
            
            # Generate invoice number
            invoice_number = cls._generate_invoice_number()
            
            # Calculate amounts
            subtotal = float(subscription.amount)
            tax_amount = cls._calculate_tax(subscription.user_id, subtotal)
            discount_amount = float(subscription.discount_amount) if subscription.discount_amount else 0.0
            total = subtotal + tax_amount - discount_amount
            
            # Create invoice
            invoice = Invoice(
                id=str(uuid.uuid4()),
                user_id=subscription.user_id,
                subscription_id=subscription_id,
                invoice_number=invoice_number,
                status='open',
                subtotal=subtotal,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                total=total,
                amount_due=total,
                currency=subscription.currency,
                due_date=datetime.utcnow() + timedelta(days=30),
                description=f"Subscription to {subscription.plan.name} ({billing_period_start.strftime('%m/%d/%Y')} - {billing_period_end.strftime('%m/%d/%Y')})"
            )
            
            db.session.add(invoice)
            
            # Create line items
            line_item = InvoiceLineItem(
                id=str(uuid.uuid4()),
                invoice_id=invoice.id,
                description=f"{subscription.plan.name} - {subscription.billing_cycle.title()} Subscription",
                quantity=1,
                unit_amount=subtotal,
                total_amount=subtotal,
                period_start=billing_period_start,
                period_end=billing_period_end
            )
            
            db.session.add(line_item)
            
            # Add discount line item if applicable
            if discount_amount > 0:
                discount_item = InvoiceLineItem(
                    id=str(uuid.uuid4()),
                    invoice_id=invoice.id,
                    description="Discount Applied",
                    quantity=1,
                    unit_amount=-discount_amount,
                    total_amount=-discount_amount
                )
                db.session.add(discount_item)
            
            # Add tax line item if applicable
            if tax_amount > 0:
                tax_item = InvoiceLineItem(
                    id=str(uuid.uuid4()),
                    invoice_id=invoice.id,
                    description="Tax",
                    quantity=1,
                    unit_amount=tax_amount,
                    total_amount=tax_amount
                )
                db.session.add(tax_item)
            
            db.session.commit()
            
            # Generate PDF
            cls.generate_pdf(invoice)
            
            # Send invoice notification
            NotificationService.send_invoice_notification(subscription.user_id, invoice.id, 'created')
            
            logger.info(f"Created invoice {invoice_number} for subscription {subscription_id}")
            
            return {
                'success': True,
                'invoice_id': invoice.id,
                'invoice_number': invoice_number,
                'total': total
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating subscription invoice: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def create_usage_invoice(cls, subscription_id: str, usage_charges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create invoice for usage-based charges"""
        try:
            subscription = Subscription.query.get(subscription_id)
            if not subscription:
                return {'success': False, 'error': 'Subscription not found'}
            
            if not usage_charges:
                return {'success': False, 'error': 'No usage charges provided'}
            
            # Generate invoice number
            invoice_number = cls._generate_invoice_number()
            
            # Calculate totals
            subtotal = sum(charge['amount'] for charge in usage_charges)
            tax_amount = cls._calculate_tax(subscription.user_id, subtotal)
            total = subtotal + tax_amount
            
            # Create invoice
            invoice = Invoice(
                id=str(uuid.uuid4()),
                user_id=subscription.user_id,
                subscription_id=subscription_id,
                invoice_number=invoice_number,
                status='open',
                subtotal=subtotal,
                tax_amount=tax_amount,
                total=total,
                amount_due=total,
                currency=subscription.currency,
                due_date=datetime.utcnow() + timedelta(days=30),
                description="Usage charges"
            )
            
            db.session.add(invoice)
            
            # Create line items for each usage charge
            for charge in usage_charges:
                line_item = InvoiceLineItem(
                    id=str(uuid.uuid4()),
                    invoice_id=invoice.id,
                    description=charge['description'],
                    quantity=charge.get('quantity', 1),
                    unit_amount=charge['amount'],
                    total_amount=charge['amount'],
                    metadata=charge.get('metadata', {})
                )
                db.session.add(line_item)
            
            # Add tax line item if applicable
            if tax_amount > 0:
                tax_item = InvoiceLineItem(
                    id=str(uuid.uuid4()),
                    invoice_id=invoice.id,
                    description="Tax",
                    quantity=1,
                    unit_amount=tax_amount,
                    total_amount=tax_amount
                )
                db.session.add(tax_item)
            
            db.session.commit()
            
            # Generate PDF
            cls.generate_pdf(invoice)
            
            # Send invoice notification
            NotificationService.send_invoice_notification(subscription.user_id, invoice.id, 'created')
            
            logger.info(f"Created usage invoice {invoice_number} for subscription {subscription_id}")
            
            return {
                'success': True,
                'invoice_id': invoice.id,
                'invoice_number': invoice_number,
                'total': total
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating usage invoice: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def generate_pdf(cls, invoice: Invoice) -> bytes:
        """Generate PDF for invoice"""
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, 
                                  leftMargin=72, topMargin=72, bottomMargin=18)
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            header_style = ParagraphStyle(
                'CustomHeader',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                textColor=colors.darkblue
            )
            
            # Build content
            content = []
            
            # Company header
            content.append(Paragraph("AssisText", title_style))
            content.append(Paragraph("SMS AI Assistant Platform", styles['Normal']))
            content.append(Spacer(1, 20))
            
            # Invoice details
            invoice_data = [
                ['Invoice Number:', invoice.invoice_number],
                ['Invoice Date:', invoice.created_at.strftime('%B %d, %Y')],
                ['Due Date:', invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'Upon Receipt'],
                ['Status:', invoice.status.title()]
            ]
            
            invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
            invoice_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            content.append(invoice_table)
            content.append(Spacer(1, 20))
            
            # Bill to section
            content.append(Paragraph("Bill To:", header_style))
            user = User.query.get(invoice.user_id)
            if user:
                bill_to_text = f"{user.first_name} {user.last_name}<br/>{user.email}"
                if hasattr(user, 'billing_address') and user.billing_address:
                    addr = user.billing_address
                    bill_to_text += f"<br/>{addr.get('line1', '')}"
                    if addr.get('line2'):
                        bill_to_text += f"<br/>{addr['line2']}"
                    bill_to_text += f"<br/>{addr.get('city', '')}, {addr.get('state', '')} {addr.get('postal_code', '')}"
                
                content.append(Paragraph(bill_to_text, styles['Normal']))
            
            content.append(Spacer(1, 20))
            
            # Line items table
            content.append(Paragraph("Invoice Details:", header_style))
            
            # Table header
            table_data = [['Description', 'Quantity', 'Unit Price', 'Total']]
            
            # Add line items
            for item in invoice.line_items:
                table_data.append([
                    item.description,
                    str(item.quantity),
                    f"${float(item.unit_amount):.2f}",
                    f"${float(item.total_amount):.2f}"
                ])
            
            # Add totals
            table_data.append(['', '', 'Subtotal:', f"${float(invoice.subtotal):.2f}"])
            
            if invoice.discount_amount and invoice.discount_amount > 0:
                table_data.append(['', '', 'Discount:', f"-${float(invoice.discount_amount):.2f}"])
            
            if invoice.tax_amount and invoice.tax_amount > 0:
                table_data.append(['', '', 'Tax:', f"${float(invoice.tax_amount):.2f}"])
            
            table_data.append(['', '', 'Total:', f"${float(invoice.total):.2f}"])
            
            # Create table
            items_table = Table(table_data, colWidths=[3.5*inch, 1*inch, 1.25*inch, 1.25*inch])
            items_table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                
                # Data rows
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                
                # Total rows styling
                ('FONTNAME', (2, -4), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (2, -1), (-1, -1), colors.lightgrey),
            ]))
            
            content.append(items_table)
            content.append(Spacer(1, 30))
            
            # Payment instructions
            content.append(Paragraph("Payment Instructions:", header_style))
            payment_text = f"""
            Please pay by the due date shown above. You can pay this invoice online through 
            your account dashboard or by contacting our billing department.<br/><br/>
            Thank you for your business!
            """
            content.append(Paragraph(payment_text, styles['Normal']))
            
            # Build PDF
            doc.build(content)
            
            # Get PDF data
            pdf_data = buffer.getvalue()
            buffer.close()
            
            # Save PDF to storage (you might want to save to S3, local file system, etc.)
            pdf_filename = f"invoice_{invoice.invoice_number}.pdf"
            pdf_path = cls._save_pdf_to_storage(pdf_filename, pdf_data)
            
            # Update invoice with PDF URL
            invoice.pdf_url = pdf_path
            db.session.commit()
            
            logger.info(f"Generated PDF for invoice {invoice.invoice_number}")
            
            return pdf_data
            
        except Exception as e:
            logger.error(f"Error generating PDF for invoice {invoice.id}: {str(e)}")
            raise
    
    @classmethod
    def get_pdf(cls, pdf_url: str) -> bytes:
        """Retrieve PDF data from storage"""
        try:
            # Implementation depends on your storage solution
            # This is a placeholder for file retrieval
            pdf_path = os.path.join(current_app.config.get('INVOICE_STORAGE_PATH', '/tmp'), pdf_url)
            
            if os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    return f.read()
            else:
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
                
        except Exception as e:
            logger.error(f"Error retrieving PDF {pdf_url}: {str(e)}")
            raise
    
    @classmethod
    def mark_invoice_paid(cls, invoice_id: str, payment_id: str) -> Dict[str, Any]:
        """Mark invoice as paid"""
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'error': 'Invoice not found'}
            
            payment = Payment.query.get(payment_id)
            if not payment:
                return {'success': False, 'error': 'Payment not found'}
            
            # Update invoice
            invoice.status = 'paid'
            invoice.amount_paid = float(payment.amount)
            invoice.amount_due = 0.0
            invoice.paid_at = payment.processed_at or datetime.utcnow()
            
            # Link payment to invoice
            payment.invoice_id = invoice_id
            
            db.session.commit()
            
            # Send payment confirmation
            NotificationService.send_invoice_notification(invoice.user_id, invoice_id, 'paid')
            
            logger.info(f"Marked invoice {invoice.invoice_number} as paid")
            
            return {'success': True, 'message': 'Invoice marked as paid'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking invoice as paid: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # Private helper methods
    
    @classmethod
    def _generate_invoice_number(cls) -> str:
        """Generate unique invoice number"""
        current_year = datetime.utcnow().year
        
        # Get the count of invoices for current year
        year_start = datetime(current_year, 1, 1)
        invoice_count = Invoice.query.filter(Invoice.created_at >= year_start).count()
        
        # Format: INV-YYYY-NNNN
        return f"INV-{current_year}-{(invoice_count + 1):04d}"
    
    @classmethod
    def _calculate_tax(cls, user_id: str, amount: float) -> float:
        """Calculate tax amount based on user location and tax rules"""
        # Simplified tax calculation - in production, integrate with tax service
        try:
            user = User.query.get(user_id)
            if not user or not hasattr(user, 'billing_address') or not user.billing_address:
                return 0.0
            
            # Basic state tax rates (example)
            tax_rates = {
                'CA': 0.08,   # California
                'NY': 0.08,   # New York
                'TX': 0.06,   # Texas
                'FL': 0.06,   # Florida
            }
            
            state = user.billing_address.get('state', '').upper()
            tax_rate = tax_rates.get(state, 0.0)
            
            return round(amount * tax_rate, 2)
            
        except Exception as e:
            logger.error(f"Error calculating tax: {str(e)}")
            return 0.0
    
    @classmethod
    def _save_pdf_to_storage(cls, filename: str, pdf_data: bytes) -> str:
        """Save PDF to storage and return path/URL"""
        try:
            # Create storage directory if it doesn't exist
            storage_path = current_app.config.get('INVOICE_STORAGE_PATH', '/tmp/invoices')
            os.makedirs(storage_path, exist_ok=True)
            
            # Save file
            file_path = os.path.join(storage_path, filename)
            with open(file_path, 'wb') as f:
                f.write(pdf_data)
            
            # Return relative path or URL
            return f"invoices/{filename}"
            
        except Exception as e:
            logger.error(f"Error saving PDF to storage: {str(e)}")
            raise

