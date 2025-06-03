import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import {
  trigger,
  state,
  style,
  animate,
  transition
} from '@angular/animations';

interface FlightLeg {
  departure_airport: string;
  departure_time: string;
  arrival_airport: string;
  arrival_time: string;
  airline: string;
  airline_logo: string;
  travel_class: string;
  flight_number: string;
  duration: number;
}

interface LayoverInfo {
  airport: string;
  airport_id: string;
  duration: number;
  overnight?: boolean;
}

interface ReturnFlight {
  airline: string;
  price: string;
  duration: string;
  stops: string;
  departure: string;
  arrival: string;
  travel_class: string;
  airline_logo: string;
  legs?: FlightLeg[];
  layovers?: LayoverInfo[];
}

interface Flight {
  airline: string;
  stops: string;
  departure: string;
  arrival: string;
  duration: string;
  price: number | string;
  travel_class: string;
  legs?: FlightLeg[];
  layovers?: LayoverInfo[];
  return_flights?: ReturnFlight[];
}

interface Hotel {
  name: string;
  price: number;
  rating: string;
  location: string;
  link: string;
}

interface SearchResponse {
  flights: Flight[];
  hotels: Hotel[];
  ai_flight_recommendation: string;
  ai_hotel_recommendation: string;
  itinerary: string;
}

@Component({
  selector: 'app-travel-planner',
  standalone: false,
  templateUrl: './travel-planner.component.html',
  styleUrls: ['./travel-planner.component.css'],
  animations: [
    trigger('collapseReturn', [
      state('void', style({ height: '0px', opacity: 0, padding: '0 10px' })),
      state('*', style({ height: '*', opacity: 1, padding: '10px' })),
      transition('void <=> *', animate('250ms cubic-bezier(.4,0,.2,1)'))
    ])
  ]
})
export class TravelPlannerComponent implements OnInit {
  travelForm: FormGroup;
  searchMode: string = 'complete';
  useFlightDestination: boolean = false;
  loading: boolean = false;
  errorMessage: string = '';
  searchResults: SearchResponse | null = null;
  activeTab: string = 'flights';
  returnFlightsOpen: { [key: number]: boolean } = {};

  private readonly API_BASE_URL = 'http://localhost:8000';

  constructor(private fb: FormBuilder, private http: HttpClient) {
    this.travelForm = this.fb.group({
      origin: ['ATL', Validators.required],
      destination: ['LAX', Validators.required],
      outboundDate: [this.getTomorrowDate(), Validators.required],
      returnDate: [this.getNextWeekDate(), Validators.required],
      location: [''],
      checkInDate: [this.getTomorrowDate(), Validators.required],
      checkOutDate: [this.getNextWeekDate(), Validators.required]
    });
  }

  ngOnInit() {
    // Set default active tab based on search mode
    this.setDefaultActiveTab();
  }

  private getTomorrowDate(): string {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  }

  private getNextWeekDate(): string {
    const nextWeek = new Date();
    nextWeek.setDate(nextWeek.getDate() + 8);
    return nextWeek.toISOString().split('T')[0];
  }

  private setDefaultActiveTab() {
    if (this.searchMode === 'flights') {
      this.activeTab = 'flights';
    } else if (this.searchMode === 'hotels') {
      this.activeTab = 'hotels';
    } else {
      this.activeTab = 'flights';
    }
  }

  onSubmit() {
    if (this.travelForm.invalid) {
      this.errorMessage = 'Please fill in all required fields.';
      return;
    }

    const formValues = this.travelForm.value;

    // Validation
    if (new Date(formValues.outboundDate) >= new Date(formValues.returnDate)) {
      this.errorMessage = 'Return date must be after departure date.';
      return;
    }

    if (new Date(formValues.checkInDate) >= new Date(formValues.checkOutDate)) {
      this.errorMessage = 'Check-out date must be after check-in date.';
      return;
    }

    this.errorMessage = '';
    this.loading = true;

    const flightData = {
      origin: formValues.origin,
      destination: formValues.destination,
      outbound_date: formValues.outboundDate,
      return_date: formValues.returnDate
    };

    const hotelLocation = this.useFlightDestination ? formValues.destination : formValues.location;
    const hotelData = {
      location: hotelLocation,
      check_in_date: formValues.checkInDate,
      check_out_date: formValues.checkOutDate
    };

    let request: Observable<SearchResponse>;

    switch (this.searchMode) {
      case 'complete':
        const completeData = {
          flight_request: flightData,
          hotel_request: hotelData
        };
        request = this.http.post<SearchResponse>(`${this.API_BASE_URL}/complete_search/`, completeData);
        break;
      case 'flights':
        request = this.http.post<SearchResponse>(`${this.API_BASE_URL}/search_flights/`, flightData);
        break;
      case 'hotels':
        request = this.http.post<SearchResponse>(`${this.API_BASE_URL}/search_hotels/`, hotelData);
        break;
      default:
        this.loading = false;
        return;
    }

    request.pipe(
      catchError(error => {
        this.errorMessage = error.error?.detail || 'An error occurred while searching.';
        this.loading = false;
        return throwError(() => error);
      })
    ).subscribe({
      next: (response) => {
        this.searchResults = response;
        this.loading = false;
        this.setDefaultActiveTab();
      },
      error: () => {
        this.loading = false;
      }
    });
  }

  getHotelLocation(): string {
    if (this.useFlightDestination) {
      return this.travelForm.get('destination')?.value || '';
    }
    return this.travelForm.get('location')?.value || '';
  }

  downloadItinerary() {
    if (this.searchResults?.itinerary) {
      const element = document.createElement('a');
      const file = new Blob([this.itineraryMarkdown], { type: 'text/markdown' });
      element.href = URL.createObjectURL(file);
      element.download = `travel_itinerary_${this.travelForm.get('destination')?.value}_${this.travelForm.get('outboundDate')?.value}.md`;
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    }
  }

  get itineraryMarkdown(): string {
    if (!this.searchResults?.itinerary) return '';
    // Remove ```markdown ... ```
    return this.searchResults.itinerary.replace(/^```markdown\s*|```$/g, '').trim();
  }
}