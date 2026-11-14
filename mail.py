import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

def send_recon_email(smtp_host: str, smtp_port: int, sender_email: str, sender_password: str, 
                     receiver_email: str, batch_name: str, summary_stats: dict, excel_bytes: bytes = None):
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = f"📊 GST Reconciliation Report — {batch_name}"

        # HTML Body Content
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
                <h2 style="color: #4f46e5; margin-top: 0;">GST Reconciliation Summary</h2>
                <p>Hello,</p>
                <p>Here is the automated reconciliation report for <strong>{batch_name}</strong> generated via GST Suite Pro.</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background-color: #f8fafc;">
                        <th style="padding: 10px; border: 1px solid #cbd5e1; text-align: left;">Metric</th>
                        <th style="padding: 10px; border: 1px solid #cbd5e1; text-align: right;">Amount / Count</th>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #cbd5e1;">Total Invoices Processed</td>
                        <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: right;"><strong>{summary_stats.get('total_bills', 0)}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #cbd5e1;">Total ERP / Books Tax</td>
                        <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: right; color: #2563eb;"><strong>₹{summary_stats.get('erp_tax', 0):,.2f}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #cbd5e1;">Total Portal 2B Tax</td>
                        <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: right; color: #16a34a;"><strong>₹{summary_stats.get('portal_tax', 0):,.2f}</strong></td>
                    </tr>
                </table>
                
                <p>Please find the detailed Excel report attached with this email.</p>
                <p style="font-size: 12px; color: #64748b; margin-top: 30px;">Generated automatically by GST Recon Pro Hub.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, 'html'))

        # Attach Excel file if provided
        if excel_bytes:
            part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            part.set_payload(excel_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="GST_Recon_{batch_name}.xlsx"')
            msg.msg_attach = msg.attach(part) # Standard attach

        # Connect and send via SMTP (e.g., Gmail TLS port 587)
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return True, "Email sent successfully!"
    except Exception as e:
        return False, str(e)