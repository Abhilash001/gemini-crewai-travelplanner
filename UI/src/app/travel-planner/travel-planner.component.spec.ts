import { TestBed, ComponentFixture, fakeAsync, tick } from '@angular/core/testing';
import { TravelPlannerComponent } from './travel-planner.component';
import { FormBuilder, FormsModule, ReactiveFormsModule } from '@angular/forms';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

describe('TravelPlannerComponent', () => {
  let component: TravelPlannerComponent;
  let fixture: ComponentFixture<TravelPlannerComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [TravelPlannerComponent],
      imports: [FormsModule, ReactiveFormsModule, HttpClientTestingModule],
      providers: [FormBuilder]
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(TravelPlannerComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
  });

  function setValidForm() {
    component.travelForm.patchValue({
      source_city: 'Mumbai',
      destination_city: 'Tokyo',
      from_date: '2025-01-01',
      return_date: '2025-01-10',
      instructions: ''
    });
  }

  it('should create the component', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize form with default values', () => {
    expect(component.travelForm).toBeTruthy();
    expect(component.travelForm.get('source_city')?.value).toBe('');
    expect(component.travelForm.get('destination_city')?.value).toBe('');
  });

  it('should set error if form is invalid', () => {
    component.travelForm.get('source_city')?.setValue('');
    component.onSubmit();
    expect(component.errorMessage).toBe('Please fill in all required fields.');
  });

  it('should set error if from_date >= return_date', () => {
    // Set all required fields to valid values first
    component.travelForm.patchValue({
      source_city: 'Mumbai',
      destination_city: 'Tokyo',
      from_date: '2025-01-10',
      return_date: '2025-01-01',
      instructions: ''
    });
    component.onSubmit();
    expect(component.errorMessage).toBe('Return date must be after departure date.');
  });

  it('should call /ai_travel_plan/ and set results on success', fakeAsync(() => {
    setValidForm();
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/ai_travel_plan/');
    expect(req.request.method).toBe('POST');
    const mockResponse = {
      flights: [{ price: 100, airline: 'TestAir', travel_class: 'Economy', duration: 120 }],
      hotels: [],
      hotels_grouped: [],
      ai_flight_recommendation: 'Test flight recommendation',
      ai_hotel_recommendations: ['Test hotel recommendation'],
      itinerary: '```markdown\n# Itinerary\n```'
    };
    req.flush(mockResponse);
    tick();
    expect(component.loading).toBe(false);
    expect(component.searchResults).toEqual(mockResponse);
    expect(component.activeTab).toBe('flights');
    expect(component.returnFlightsOpen.length).toBe(1);
  }));

  it('should set errorMessage on API error', fakeAsync(() => {
    setValidForm();
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/ai_travel_plan/');
    req.flush({ detail: 'API error' }, { status: 400, statusText: 'Bad Request' });
    tick();
    expect(component.errorMessage).toBe('API error');
    expect(component.loading).toBe(false);
  }));

  it('should not throw if downloadItinerary called with no results', () => {
    component.searchResults = null;
    expect(() => component.downloadItinerary()).not.toThrow();
  });

  it('should not throw if downloadItineraryPdf called with no results', () => {
    component.searchResults = null;
    expect(() => component.downloadItineraryPdf()).not.toThrow();
  });

  it('should not throw if downloadItineraryPdf called with empty itinerary', () => {
    component.searchResults = { itinerary: '' };
    expect(() => component.downloadItineraryPdf()).not.toThrow();
  });

  it('itineraryMarkdown should strip markdown fences', () => {
    component.searchResults = { itinerary: '```markdown\n# Test\n```' };
    expect(component.itineraryMarkdown).toBe('# Test');
  });

  it('itineraryMarkdown should return empty string if no itinerary', () => {
    component.searchResults = null;
    expect(component.itineraryMarkdown).toBe('');
    component.searchResults = { itinerary: '' };
    expect(component.itineraryMarkdown).toBe('');
  });

  it('itineraryMarkdown should handle undefined itinerary gracefully', () => {
    component.searchResults = {};
    expect(component.itineraryMarkdown).toBe('');
  });

  it('formatDuration should format minutes correctly', () => {
    expect(component.formatDuration(130)).toBe('2 hr 10 min');
    expect(component.formatDuration(60)).toBe('1 hr');
    expect(component.formatDuration(45)).toBe('45 min');
    expect(component.formatDuration('90')).toBe('1 hr 30 min');
    expect(component.formatDuration(-5)).toBe('');
    expect(component.formatDuration('bad')).toBe('');
    expect(component.formatDuration(0)).toBe('');
    expect(component.formatDuration(' 120 ')).toBe('2 hr');
  });

  it('formatDuration should handle null and undefined', () => {
    expect(component.formatDuration(null as any)).toBe('');
    expect(component.formatDuration(undefined as any)).toBe('');
  });

  it('should disable submit button when form is invalid', () => {
    component.travelForm.get('source_city')?.setValue('');
    fixture.detectChanges();
    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button[type="submit"]');
    expect(button.disabled).toBeTrue();
  });

  it('should set loading to true when submitting and false after response', fakeAsync(() => {
    setValidForm();
    component.onSubmit();
    expect(component.loading).toBeTrue();
    const req = httpMock.expectOne('http://localhost:8000/ai_travel_plan/');
    req.flush({});
    tick();
    expect(component.loading).toBeFalse();
  }));

  it('should toggle returnFlightsOpen for a flight', fakeAsync(() => {
    setValidForm();
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/ai_travel_plan/');
    const mockResponse = {
      flights: [
        { price: 100, airline: 'TestAir', travel_class: 'Economy', duration: 120, return_flights: [{}] }
      ],
      hotels: [],
      hotels_grouped: [],
      ai_flight_recommendation: '',
      ai_hotel_recommendations: [],
      itinerary: ''
    };
    req.flush(mockResponse);
    tick();
    expect(component.returnFlightsOpen[0]).toBeFalse();
    component.returnFlightsOpen[0] = !component.returnFlightsOpen[0];
    expect(component.returnFlightsOpen[0]).toBeTrue();
  }));

  it('downloadItinerary should do nothing if no itinerary', () => {
    spyOn(document, 'createElement');
    component.searchResults = {};
    component.downloadItinerary();
    expect(document.createElement).not.toHaveBeenCalled();
  });
});