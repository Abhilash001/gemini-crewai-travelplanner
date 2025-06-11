import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Component({
  selector: 'app-travel-planner',
  standalone: false,
  templateUrl: './travel-planner.component.html',
  styleUrls: ['./travel-planner.component.css']
})
export class TravelPlannerComponent implements OnInit {
  travelForm: FormGroup;
  loading = false;
  errorMessage = '';
  searchResults: any = null;
  activeTab: string = 'flights';

  // Add this property to manage return flight toggles
  returnFlightsOpen: boolean[] = [];

  private readonly API_BASE_URL = 'http://localhost:8000';

  constructor(private fb: FormBuilder, private http: HttpClient) {
    this.travelForm = this.fb.group({
      source_city: ['', Validators.required],
      destination_city: ['', Validators.required],
      from_date: ['', Validators.required],
      return_date: ['', Validators.required],
      instructions: ['']
    });
  }

  ngOnInit() {}

  onSubmit() {
    if (this.travelForm.invalid) {
      this.errorMessage = 'Please fill in all required fields.';
      return;
    }
    const formValues = this.travelForm.value;
    if (new Date(formValues.from_date) >= new Date(formValues.return_date)) {
      this.errorMessage = 'Return date must be after departure date.';
      return;
    }
    this.errorMessage = '';
    this.loading = true;
    this.searchResults = null;
    this.returnFlightsOpen = []; // Reset toggles on new search

    this.http.post<any>(`${this.API_BASE_URL}/ai_travel_plan/`, formValues)
      .pipe(
        catchError(error => {
          this.errorMessage = error.error?.detail || 'An error occurred while searching.';
          this.loading = false;
          return throwError(() => error);
        })
      )
      .subscribe({
        next: (response) => {
          this.searchResults = response;
          this.loading = false;
          this.activeTab = 'flights';
          // Initialize toggles for each flight
          this.returnFlightsOpen = (response.flights || []).map(() => false);
        },
        error: () => {
          this.loading = false;
        }
      });
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
    if (minutes === null || minutes === undefined) return '';
    const min = typeof minutes === 'string' ? parseInt(minutes, 10) : minutes;
    if (isNaN(min) || min <= 0) return '';
    const hr = Math.floor(min / 60);
    const rem = min % 60;
    if (hr > 0 && rem > 0) return `${hr} hr ${rem} min`;
    if (hr > 0) return `${hr} hr`;
    return `${rem} min`;
  }
}