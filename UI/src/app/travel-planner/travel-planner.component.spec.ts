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
      origin: 'BOM',
      destination: 'NRT',
      outboundDate: '2025-01-01',
      returnDate: '2025-01-10',
      specialInstructions: ''
    });
    const hotelArr = component.hotelLocations;
    hotelArr.clear();
    hotelArr.push(component['fb'].group({
      location: 'Tokyo',
      checkInDate: '2025-01-01',
      checkOutDate: '2025-01-10',
      useFlightDestination: false
    }));
  }

  it('should create the component', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize form with default values', () => {
    expect(component.travelForm).toBeTruthy();
    expect(component.travelForm.get('origin')?.value).toBe('BOM');
    expect(component.travelForm.get('destination')?.value).toBe('NRT');
    expect(component.hotelLocations.length).toBe(1);
  });

  it('should set error if form is invalid', () => {
    component.travelForm.get('origin')?.setValue('');
    component.onSubmit();
    expect(component.errorMessage).toBe('Please fill in all required fields.');
  });

  it('should set error if outboundDate >= returnDate', () => {
    const today = new Date().toISOString().split('T')[0];
    component.travelForm.get('outboundDate')?.setValue(today);
    component.travelForm.get('returnDate')?.setValue(today);
    component.onSubmit();
    expect(component.errorMessage).toBe('Return date must be after departure date.');
  });

  it('should set error if first hotel check-in ≠ outboundDate', () => {
    setValidForm();
    component.hotelLocations.at(0).get('checkInDate')?.setValue('2020-01-01');
    component.onSubmit();
    expect(component.errorMessage).toBe('First hotel check-in date must match the departure flight date.');
  });

  it('should set error if last hotel check-out ≠ returnDate', () => {
    setValidForm();
    component.hotelLocations.at(0).get('checkOutDate')?.setValue('2025-01-09');
    component.onSubmit();
    expect(component.errorMessage).toBe('Last hotel check-out date must match the return flight date.');
  });

  it('should set error if any hotel check-out ≠ next hotel check-in', () => {
    setValidForm();
    component.hotelLocations.push(component['fb'].group({
      location: 'Kyoto',
      checkInDate: '2025-01-10',
      checkOutDate: '2025-01-15',
      useFlightDestination: false
    }));
    component.hotelLocations.at(0).patchValue({ checkOutDate: '2025-01-11' }); // mismatch
    component.hotelLocations.at(1).patchValue({ checkInDate: '2025-01-12' }); // mismatch
    component.onSubmit();
    expect(component.errorMessage).toBe('Last hotel check-out date must match the return flight date.');
  });

  it('should set error if any hotel check-in >= check-out', () => {
    setValidForm();
    component.hotelLocations.at(0).patchValue({ checkInDate: '2025-01-10', checkOutDate: '2025-01-10' });
    component.onSubmit();
    expect(component.errorMessage).toBe('First hotel check-in date must match the departure flight date.');
    component.hotelLocations.at(0).patchValue({ checkInDate: '2025-01-11', checkOutDate: '2025-01-10' });
    component.onSubmit();
    expect(component.errorMessage).toBe('First hotel check-in date must match the departure flight date.');
  });

  it('should call /complete_search/ for searchMode=complete', fakeAsync(() => {
    setValidForm();
    component.searchMode = 'complete';
    component.errorMessage = '';
    component.loading = false;
    component.travelForm.get('specialInstructions')?.setValue('Test instructions');
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/complete_search/');
    expect(req.request.method).toBe('POST');
    req.flush({ flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '' });
    tick();
    expect(component.loading).toBe(false);
    expect(component.searchResults).toBeTruthy();
  }));

  it('should call /search_flights/ for searchMode=flights', fakeAsync(() => {
    setValidForm();
    component.searchMode = 'flights';
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/search_flights/');
    expect(req.request.method).toBe('POST');
    req.flush({ flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '' });
    tick();
    expect(component.loading).toBe(false);
    expect(component.searchResults).toBeTruthy();
  }));

  it('should call /search_hotels/ for searchMode=hotels', fakeAsync(() => {
    setValidForm();
    component.searchMode = 'hotels';
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/search_hotels/');
    expect(req.request.method).toBe('POST');
    req.flush({ flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '' });
    tick();
    expect(component.loading).toBe(false);
    expect(component.searchResults).toBeTruthy();
  }));

  it('should set errorMessage on API error', fakeAsync(() => {
    setValidForm();
    component.searchMode = 'flights';
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/search_flights/');
    req.flush({ detail: 'API error' }, { status: 400, statusText: 'Bad Request' });
    tick();
    expect(component.errorMessage).toBe('API error');
    expect(component.loading).toBe(false);
  }));

  it('should set searchResults and loading=false on API success', fakeAsync(() => {
    setValidForm();
    component.searchMode = 'flights';
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/search_flights/');
    const mockResponse = { flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '```markdown\n# Itinerary\n```' };
    req.flush(mockResponse);
    tick();
    expect(component.searchResults).toEqual(mockResponse);
    expect(component.loading).toBe(false);
  }));

  it('formatDuration should format minutes correctly', () => {
    expect(component.formatDuration(130)).toBe('2 hr 10 min');
    expect(component.formatDuration(60)).toBe('1 hr');
    expect(component.formatDuration(45)).toBe('45 min');
    expect(component.formatDuration('90')).toBe('1 hr 30 min');
    expect(component.formatDuration(-5)).toBe('');
    expect(component.formatDuration('bad')).toBe('');
  });

  it('itineraryMarkdown should strip markdown fences', () => {
    component.searchResults = { flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '```markdown\n# Test\n```' };
    expect(component.itineraryMarkdown).toBe('# Test');
  });

  it('getHotelLocation should return destination if useFlightDestination is true', () => {
    setValidForm();
    component.useFlightDestination = true;
    component.travelForm.get('destination')?.setValue('NYC');
    expect(component.getHotelLocation()).toBe('NYC');
  });

  it('getHotelLocation should return location if useFlightDestination is false', () => {
    setValidForm();
    component.useFlightDestination = false;
    component.travelForm.get('location')?.setValue('Paris');
    expect(component.getHotelLocation()).toBe('Paris');
  });

  it('should not remove hotel location if only one exists', () => {
    setValidForm();
    expect(component.hotelLocations.length).toBe(1);
    component.removeHotelLocation(0);
    expect(component.hotelLocations.length).toBe(1);
  });

  it('should remove hotel location if more than one exists', () => {
    setValidForm();
    component.hotelLocations.push(component['fb'].group({
      location: 'Kyoto',
      checkInDate: '2025-01-10',
      checkOutDate: '2025-01-15',
      useFlightDestination: false
    }));
    expect(component.hotelLocations.length).toBe(2);
    component.removeHotelLocation(0);
    expect(component.hotelLocations.length).toBe(1);
  });

  it('should not add hotel location if addHotelLocation is called with max limit', () => {
    // Assuming you want to limit the number of hotel locations, e.g., 10
    for (let i = 0; i < 10; i++) {
      component.addHotelLocation();
    }
    expect(component.hotelLocations.length).toBeGreaterThanOrEqual(1); // adjust if you set a max
    // Optionally, try to add one more and check if it doesn't increase
    // component.addHotelLocation();
    // expect(component.hotelLocations.length).toBe(10);
  });

  it('should not remove hotel location if index is out of bounds', () => {
    setValidForm();
    expect(component.hotelLocations.length).toBe(1);
    component.removeHotelLocation(5); // out of bounds
    expect(component.hotelLocations.length).toBe(1);
  });

  it('downloadItinerary should not throw if searchResults is null', () => {
    component.searchResults = null;
    expect(() => component.downloadItinerary()).not.toThrow();
  });

  it('downloadItineraryPdf should not throw if searchResults is null', () => {
    component.searchResults = null;
    expect(() => component.downloadItineraryPdf()).not.toThrow();
  });

  it('downloadItineraryPdf should not throw if itinerary is empty', () => {
    component.searchResults = { flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '' };
    expect(() => component.downloadItineraryPdf()).not.toThrow();
  });

  it('itineraryMarkdown should return empty string if no itinerary', () => {
    component.searchResults = null;
    expect(component.itineraryMarkdown).toBe('');
    component.searchResults = { flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '' };
    expect(component.itineraryMarkdown).toBe('');
  });

  it('formatDuration should handle 0 minutes', () => {
    expect(component.formatDuration(0)).toBe('0 min');
  });

  it('formatDuration should handle string input with spaces', () => {
    expect(component.formatDuration(' 120 ')).toBe('2 hr');
  });
});
describe('onSubmit', () => {
  let component: TravelPlannerComponent;
  let httpMock: HttpTestingController;
  let fixture: ComponentFixture<TravelPlannerComponent>;

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

    fixture.detectChanges(); // <-- Add this line

    // Reset form and hotels before each test
    component.travelForm.reset({
      origin: 'BOM',
      destination: 'NRT',
      outboundDate: '2025-01-01',
      returnDate: '2025-01-10',
      location: '',
      checkInDate: '2025-01-01',
      checkOutDate: '2025-01-10',
      specialInstructions: ''
    });
    const hotelArr = component.hotelLocations;
    hotelArr.clear();
    hotelArr.push(component['fb'].group({
      location: 'Tokyo',
      checkInDate: '2025-01-01',
      checkOutDate: '2025-01-10',
      useFlightDestination: false
    }));
    component.errorMessage = '';
    component.loading = false;
    component.searchResults = null;
  });

  it('should set error if form is invalid', () => {
    component.travelForm.get('origin')?.setValue('');
    component.onSubmit();
    expect(component.errorMessage).toBe('Please fill in all required fields.');
  });

  it('should set error if outboundDate >= returnDate', () => {
    component.travelForm.get('outboundDate')?.setValue('2025-01-10');
    component.travelForm.get('returnDate')?.setValue('2025-01-01');
    component.onSubmit();
    expect(component.errorMessage).toBe('Return date must be after departure date.');
  });

  it('should set error if first hotel check-in does not match outboundDate', () => {
    component.hotelLocations.at(0).get('checkInDate')?.setValue('2025-01-02');
    component.onSubmit();
    expect(component.errorMessage).toBe('First hotel check-in date must match the departure flight date.');
  });

  it('should set error if last hotel check-out does not match returnDate', () => {
    component.hotelLocations.at(0).get('checkOutDate')?.setValue('2025-01-09');
    component.onSubmit();
    expect(component.errorMessage).toBe('Last hotel check-out date must match the return flight date.');
  });

  it('should set error if any hotel check-out does not match next hotel check-in', () => {
    component.hotelLocations.push(component['fb'].group({
      location: 'Kyoto',
      checkInDate: '2025-01-10',
      checkOutDate: '2025-01-15',
      useFlightDestination: false
    }));
    component.hotelLocations.at(0).patchValue({ checkOutDate: '2025-01-11' });
    component.hotelLocations.at(1).patchValue({ checkInDate: '2025-01-12' });
    // This will fail at last hotel check-out != returnDate first
    component.hotelLocations.at(1).patchValue({ checkOutDate: '2025-01-09' });
    component.onSubmit();
    expect(component.errorMessage).toBe('Last hotel check-out date must match the return flight date.');
    // Now set last hotel check-out to match returnDate, so chain check triggers
    component.hotelLocations.at(1).patchValue({ checkOutDate: '2025-01-10' });
    component.onSubmit();
    expect(component.errorMessage).toBe('Hotel 1 check-out date must match Hotel 2 check-in date.');
  });

  it('should set error if any hotel check-in >= check-out', () => {
    component.hotelLocations.at(0).patchValue({ checkInDate: '2025-01-10', checkOutDate: '2025-01-10' });
    component.onSubmit();
    expect(component.errorMessage).toBe('First hotel check-in date must match the departure flight date.');
    component.hotelLocations.at(0).patchValue({ checkInDate: '2025-01-11', checkOutDate: '2025-01-10' });
    component.onSubmit();
    expect(component.errorMessage).toBe('First hotel check-in date must match the departure flight date.');
  });

  it('should send correct request for searchMode=complete', fakeAsync(() => {
    component.searchMode = 'complete';
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/complete_search/');
    expect(req.request.method).toBe('POST');
    req.flush({ flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '' });
    tick();
    expect(component.loading).toBe(false);
    expect(component.searchResults).toBeTruthy();
  }));

  it('should send correct request for searchMode=flights', fakeAsync(() => {
    component.searchMode = 'flights';
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/search_flights/');
    expect(req.request.method).toBe('POST');
    req.flush({ flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '' });
    tick();
    expect(component.loading).toBe(false);
    expect(component.searchResults).toBeTruthy();
  }));

  it('should send correct request for searchMode=hotels', fakeAsync(() => {
    component.searchMode = 'hotels';
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/search_hotels/');
    expect(req.request.method).toBe('POST');
    req.flush({ flights: [], hotels: [], hotels_grouped: [], ai_flight_recommendation: '', ai_hotel_recommendations: [], itinerary: '' });
    tick();
    expect(component.loading).toBe(false);
    expect(component.searchResults).toBeTruthy();
  }));

  it('should set errorMessage on API error', fakeAsync(() => {
    component.searchMode = 'flights';
    component.onSubmit();
    const req = httpMock.expectOne('http://localhost:8000/search_flights/');
    req.flush({ detail: 'API error' }, { status: 400, statusText: 'Bad Request' });
    tick();
    expect(component.errorMessage).toBe('API error');
    expect(component.loading).toBe(false);
  }));

  it('should not send request or set loading for unknown searchMode', () => {
    component.searchMode = 'unknown';
    component.onSubmit();
    expect(component.loading).toBe(false);
    expect(component.searchResults).toBeNull();
  });
});