export interface Campaign {
  id:                  number
  name:                string
  status:              string
  dial_mode:           string
  leads_total:         number
  leads_called:        number
  leads_answered:      number
  caller_id_pool?:     string
  predictive_ratio?:   number
  ring_timeout_seconds?: number
  allowed_hours_start?: number
  allowed_hours_end?:   number
  allowed_timezone?:    string
  allowed_weekdays?:    string
}

export interface Lead {
  id:           number
  name:         string
  numero_1:     string
  numero_2?:    string
  numero_3?:    string
  phones?:      string[]
  email?:       string
  company_name?: string
  job_title?:   string
  status:       string
  campaign_id:  number
  notes?:       string
  created_at:   string
}

export interface Call {
  id:               number
  lead_name?:       string
  phone_dialed?:    string
  phone_number?:    string
  status:           string
  duration_seconds?: number
  duration?:        number
  created_at:       string
  campaign_id?:     number
  campaign_name?:   string
  disposition?:     string
  answered_by?:     string
  hangup_cause?:    string
}

export interface Agent {
  id:          number
  name:        string
  status:      string
  last_active: string | null
  active_call: {
    conference_name: string
    status:          string
    lead_name?:      string
    phone_number?:   string
  } | null
}

export interface DashboardMetrics {
  total_calls:     number
  answered_calls:  number
  total_leads:     number
  active_sessions: number
  answer_rate:     number
  avg_duration:    number
  calls_today:     number
  credit_balance?: number
}

export interface FollowUpSequence {
  id:           number
  name:         string
  trigger:      string
  steps:        FollowUpStep[]
  campaign_id?: number
}

export interface FollowUpStep {
  delay_minutes: number
  action:        'email' | 'whatsapp' | 'ligar'
  template:      string
}

export interface FollowUpTask {
  id:            number
  sequence_name?: string
  lead_id:       number
  lead_name?:    string
  action:        string
  template:      string
  scheduled_at:  string
  status:        string
  executed_at?:  string
}

export interface DncEntry {
  id:         number
  phone:      string
  reason?:    string
  created_at: string
}

export interface CallbackItem {
  id:            number
  lead_id:       number
  lead_name?:    string
  phone:         string
  notes?:        string
  scheduled_for?: string
  scheduled_at?: string
  status:        string
  priority:      string
}

export interface User {
  id:         number
  name:       string
  email:      string
  role:       string
  created_at: string
}
