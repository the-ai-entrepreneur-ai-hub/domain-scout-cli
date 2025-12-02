import scrapy


class LegalNoticeItem(scrapy.Item):
    """Item for storing extracted legal notice data"""
    domain = scrapy.Field()
    url = scrapy.Field()
    company_name = scrapy.Field()
    legal_form = scrapy.Field()
    street = scrapy.Field()
    postal_code = scrapy.Field()
    city = scrapy.Field()
    country = scrapy.Field()
    ceo_names = scrapy.Field()
    emails = scrapy.Field()
    phone_numbers = scrapy.Field()
    fax_numbers = scrapy.Field()
    registration_number = scrapy.Field()
    vat_id = scrapy.Field()
    owner_organization = scrapy.Field()
    industry = scrapy.Field()
    company_size = scrapy.Field()
    service_product_description = scrapy.Field()
    social_links = scrapy.Field()
    raw_html = scrapy.Field()
    extracted_text = scrapy.Field()
    
    # Whois Data
    whois_registrar = scrapy.Field()
    whois_creation_date = scrapy.Field()
    whois_expiration_date = scrapy.Field()
    whois_owner = scrapy.Field()
    whois_emails = scrapy.Field()
