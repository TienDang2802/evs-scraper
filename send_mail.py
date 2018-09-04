import os
import sendgrid
from sendgrid.helpers.mail import *
from sendgrid import *
import base64

def send_mail(to_email_address, subject, body, cc_email_address = None):
    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))

    from_email = Email(os.environ.get('SENDER_EMAIL'))
    to_email = Email(to_email_address)

    content = Content("text/html", body)
    mail = Mail(from_email, subject, to_email, content)

    if cc_email_address is not None:
        mail.personalizations[0].add_to(Email(cc_email_address))

    response = sg.client.mail.send.post(request_body=mail.get())

    if response.status_code != 202:
        return 'An error occurred: {}'.format(response.body), 500

    print('Sent email success')


def send_mail_attachment(mail_address, user, uid):
    cc_email_address = os.environ.get('BCC_EMAIL')
    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))

    from_email = Email(os.environ.get('SENDER_EMAIL'))
    to_email = Email(mail_address)

    subject = "Freshly scraped leads in your inbox"

    file_name = str(user) + str(uid) + '_leads.csv'

    # count how many leads are in the csv
    with open(file_name) as csvfile:
        row_count = sum(1 for row in csvfile)
        row_count = row_count - 1

    body = "Dear " + str(user) + ",\nyou can find " + str(row_count) + " freshly scraped leads attached!"
    content = Content("text/html", body)

    mail = Mail(from_email, subject, to_email, content)

    with open(file_name, 'rb') as fd:
        data = fd.read()
        fd.close()

    b64data = base64.b64encode(data).decode()

    mail.personalizations[0].add_to(Email(cc_email_address))

    attachment = Attachment()
    attachment.content = b64data
    attachment.filename = file_name
    mail.add_attachment(attachment)

    response = sg.client.mail.send.post(request_body=mail.get())

    if response.status_code != 202:
        return 'An error occurred: {}'.format(response.body), 500

    print('Sent email success')


def notify_admin(query, city, email, filters_include, filters_exclude, user, max_leads):
    to_addr = os.environ.get('NOTIFY_EMAIL')

    subject = str(user) + " requested " + str(max_leads) + " leads"

    body = "Query: " + str(query) + "\nCity: " + str(city) + "\nEmail: " + str(email) + "\nInclude: " + str(filters_include) + "\nExclude: " + str(filters_exclude) + "\n\nCheck heroku worker logs"

    send_mail(to_addr, subject, body)


if __name__ == '__main__':
    send_mail()
