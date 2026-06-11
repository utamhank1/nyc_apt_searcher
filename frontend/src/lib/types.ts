export interface Listing {
  id: number;
  source: string;
  source_id: string;
  url: string;
  title: string;
  price: number | null;
  beds: number | null;
  baths: number | null;
  sqft: number | null;
  address: string | null;
  neighborhood: string | null;
  borough: string | null;
  amenities: string[];
  images: string[];
  broker_name: string | null;
  broker_email: string | null;
  broker_phone: string | null;
  available_date: string | null;
  search_name: string | null;
  open_house_dates: Array<{ date: string; start_time: string; end_time: string }>;
  description: string | null;
  commute_minutes: number | null;
  match_score: number | null;
  status: string;
  lead_response: string | null;
  notified: boolean;
  is_favorite: boolean;
  is_active: boolean;
  first_seen: string | null;
  broker_email_sent: boolean;
}

export interface LeadsResponse {
  items: Listing[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface SearchConfig {
  boroughs: string[];
  neighborhoods: string[];
  max_price: number;
  min_price: number;
  min_beds: number;
  min_baths: number;
  must_have_amenities: string[];
  preferred_amenities: string[];
  work_address: string;
  lead_score_threshold: number;
  sources_enabled: Record<string, boolean>;
  move_in_mode: string;
  move_in_date: string;
  move_in_range_start: string;
  move_in_range_end: string;
  move_in_only: boolean;
  search_partner_emails: string[];
  user_name: string;
  user_email: string;
  user_phone: string;
  use_custom_email_template: boolean;
  custom_email_subject: string;
  custom_email_body: string;
}

export interface Stats {
  total_listings: number;
  active_listings: number;
  hot_leads: number;
  tours_scheduled: number;
  broker_emails_sent: number;
  passed: number;
  last_scrape: string | null;
}

export const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-100 text-blue-800",
  alerted: "bg-cyan-100 text-cyan-800",
  pending: "bg-yellow-100 text-yellow-800",
  tour_scheduled: "bg-green-100 text-green-800",
  visited: "bg-purple-100 text-purple-800",
  applied: "bg-indigo-100 text-indigo-800",
  passed: "bg-gray-100 text-gray-600",
};

export const STATUS_LABELS: Record<string, string> = {
  new: "New",
  alerted: "Alerted",
  pending: "Pending",
  tour_scheduled: "Tour Scheduled",
  visited: "Visited",
  applied: "Applied",
  passed: "Passed",
};

export const ALL_BOROUGHS = [
  "Manhattan",
  "Brooklyn",
  "Queens",
  "Bronx",
  "Staten Island",
];

export const NEIGHBORHOODS_BY_BOROUGH: Record<string, string[]> = {
  Manhattan: [
    "Chelsea", "East Harlem", "East Village", "Financial District",
    "Flatiron", "Gramercy Park", "Greenwich Village", "Harlem",
    "Hell's Kitchen", "Inwood", "Kips Bay", "Lower East Side",
    "Midtown East", "Midtown West", "Murray Hill", "NoHo", "Nolita",
    "SoHo", "Tribeca", "Upper East Side", "Upper West Side",
    "Washington Heights", "West Village",
  ],
  Brooklyn: [
    "Bay Ridge", "Bed-Stuy", "Boerum Hill", "Brooklyn Heights",
    "Bushwick", "Carroll Gardens", "Cobble Hill", "Crown Heights",
    "Downtown Brooklyn", "DUMBO", "Fort Greene", "Greenpoint",
    "Park Slope", "Prospect Heights", "Sunset Park", "Williamsburg",
  ],
  Queens: [
    "Astoria", "Flushing", "Forest Hills", "Jackson Heights",
    "Long Island City", "Sunnyside",
  ],
  Bronx: [
    "Concourse", "Fordham", "Mott Haven", "Riverdale",
  ],
  "Staten Island": [
    "St. George", "Tompkinsville",
  ],
};

export interface SavedSearch {
  id: number;
  name: string;
  is_active: boolean;
  boroughs: string[];
  neighborhoods: string[];
  max_price: number;
  min_price: number;
  min_beds: number;
  min_baths: number;
  must_have_amenities: string[];
  preferred_amenities: string[];
  work_address: string;
  lead_score_threshold: number;
  sources_enabled: Record<string, boolean>;
  move_in_mode: string;
  move_in_date: string;
  move_in_range_start: string;
  move_in_range_end: string;
  move_in_only: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export const ALL_AMENITIES = [
  "dishwasher",
  "washer/dryer in unit",
  "laundry in building",
  "doorman",
  "elevator",
  "gym",
  "roof access",
  "outdoor space",
  "pets allowed",
  "air conditioning",
  "parking available",
  "storage available",
  "concierge",
];
