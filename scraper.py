import urllib.request
import json
import re

def scrape_products():
    url = "https://www.lestepuys.com/wp-json/wc/store/v1/products?per_page=100"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        res = urllib.request.urlopen(req)
        data = json.loads(res.read().decode('utf-8'))

        products_by_category = {
            "Charcuterie": [],
            "Plateaux de dégustation": [],
            "Boissons": [],
            "Tartinables": []
        }

        cat_mapping = {
            "Charcuterie": "Charcuterie",
            "Box et plateaux": "Plateaux de dégustation",
            "Boissons": "Boissons",
            "Tartinables": "Tartinables"
        }

        for item in data:
            item_cats = [c['name'] for c in item.get('categories', [])]
            name = item.get('name', '').strip()
            # Clean HTML entities from name if any
            name = name.replace('&rsquo;', "'").replace('&amp;', '&')

            # price in cents or string
            raw_price = item.get('prices', {}).get('price', '0')
            try:
                price = float(raw_price) / 100.0 if raw_price else 0.0
            except ValueError:
                price = 0.0

            # If price is 0, give a default reasonable price if appropriate, or keep price
            images = item.get('images', [])
            image_url = images[0].get('src') if images else None

            description = item.get('short_description', '') or item.get('description', '')
            # Strip tags from description
            description = re.sub('<[^<]+?>', '', description).strip()

            for c in item_cats:
                if c in cat_mapping:
                    target_cat = cat_mapping[c]
                    products_by_category[target_cat].append({
                        "name": name,
                        "price": price if price > 0 else 5.50, # reasonable fallback if 0 on WooCommerce backend
                        "description": description,
                        "image_url": image_url
                    })
                    break

        return products_by_category
    except Exception as e:
        print("Error scraping:", e)
        return {}

if __name__ == "__main__":
    data = scrape_products()
    for cat, prods in data.items():
        print(f"Category {cat}: {len(prods)} products found")
        for p in prods[:3]:
            print("  ", p)
    with open("scraped_products.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved scraped products to scraped_products.json")
