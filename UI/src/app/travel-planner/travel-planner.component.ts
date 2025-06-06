import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators, FormArray } from '@angular/forms';
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
  price: number;
  duration: number;
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
  duration: number;
  price: number;
  travel_class: string;
  legs?: FlightLeg[];
  layovers?: LayoverInfo[];
  return_flights?: ReturnFlight[];
}

interface Hotel {
  name: string;
  price: number;
  rating: number;
  location: string;
  link: string;
}

interface HotelsGrouped {
  location: string;
  check_in_date: string;
  check_out_date: string;
  hotels: Hotel[];
}

interface SearchResponse {
  flights: Flight[];
  hotels: Hotel[];
  hotels_grouped: HotelsGrouped[];
  ai_flight_recommendation: string;
  ai_hotel_recommendations: string[];
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
      origin: ['BOM', Validators.required],
      destination: ['NRT', Validators.required],
      outboundDate: [this.getTomorrowDate(), Validators.required],
      returnDate: [this.getNextWeekDate(), Validators.required],
      location: [''],
      checkInDate: [this.getTomorrowDate(), Validators.required],
      checkOutDate: [this.getNextWeekDate(), Validators.required]
    });
  }

  ngOnInit() {
    // Initialize hotelLocations with one entry
    if (!this.travelForm.get('hotelLocations')) {
      this.travelForm.addControl('hotelLocations', this.fb.array([]));
      this.addHotelLocation();
    }
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

  get hotelLocations(): FormArray {
    return this.travelForm.get('hotelLocations') as FormArray;
  }

  addHotelLocation() {
    this.hotelLocations.push(this.fb.group({
      location: [''],
      checkInDate: [this.getTomorrowDate(), Validators.required],
      checkOutDate: [this.getNextWeekDate(), Validators.required],
      useFlightDestination: [false]
    }));
  }

  removeHotelLocation(index: number) {
    if (this.hotelLocations.length > 1) {
      this.hotelLocations.removeAt(index);
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

    const hotelRequests = this.hotelLocations.controls.map((ctrl: any) => {
      const val = ctrl.value;
      return {
        location: val.useFlightDestination ? this.travelForm.get('destination')?.value : val.location,
        check_in_date: val.checkInDate,
        check_out_date: val.checkOutDate
      };
    });

    let request: Observable<SearchResponse>;

    switch (this.searchMode) {
      case 'complete':
        const completeData = {
          flight_request: flightData,
          hotel_request: hotelRequests
        };
        request = this.http.post<SearchResponse>(`${this.API_BASE_URL}/complete_search/`, completeData);
        break;
      case 'flights':
        request = this.http.post<SearchResponse>(`${this.API_BASE_URL}/search_flights/`, flightData);
        break;
      case 'hotels':
        request = this.http.post<SearchResponse>(`${this.API_BASE_URL}/search_hotels/`, hotelRequests);
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

  downloadItineraryPdf() {
    if (!this.searchResults?.itinerary) return;
    const markdown = this.itineraryMarkdown;
    const title = `travel_itinerary_${this.travelForm.get('destination')?.value}_${this.travelForm.get('outboundDate')?.value}`;
    this.http.post(
      `${this.API_BASE_URL}/generate_pdf/`,
      { markdown, title },
      { responseType: 'blob' }
    ).subscribe(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    });
  }

  get itineraryMarkdown(): string {
    if (!this.searchResults?.itinerary) return '';
    // Remove ```markdown ... ```
    return this.searchResults.itinerary.replace(/^```markdown\s*|```$/g, '').trim();
  }

  formatDuration(minutes: number | string): string {
    const min = typeof minutes === 'string' ? parseInt(minutes, 10) : minutes;
    if (isNaN(min) || min < 0) return '';
    const hr = Math.floor(min / 60);
    const rem = min % 60;
    if (hr > 0 && rem > 0) return `${hr} hr ${rem} min`;
    if (hr > 0) return `${hr} hr`;
    return `${rem} min`;
  }
}